import asyncio
import logging
from typing import Any, Dict

from analyst.application.agents.fundamentals import FundamentalsAgent
from analyst.application.agents.planner import PlannerAgent
from analyst.application.agents.share_price import SharePriceAgent
from analyst.application.agents.synthesizer import SynthesizerAgent
from analyst.application.agents.tools import DataTools
from analyst.application.agents.valuation import ValuationAgent
from analyst.application.agents.news_agent import NewsAgent
from analyst.application.analysis.models import AnalysisResult
from common.llm.client import LlmClient
from common.requests.analyze_ticker import AnalyzeTickerRequest

logger = logging.getLogger(__name__)


class AnalysisWorkflow:
    """
    Orchestrates the multi-agent workflow for performing a deep analysis of a
    specific stock ticker.
    """

    def __init__(self, llm_client: LlmClient, tools: DataTools):
        self._llm_client = llm_client
        self._tools = tools
        self._planner = PlannerAgent(llm_client, tools)
        self._fundamentals = FundamentalsAgent(llm_client, tools)
        self._share_price = SharePriceAgent(llm_client, tools)
        self._valuation = ValuationAgent(llm_client, tools)
        self._news = NewsAgent(llm_client, tools)
        self._synthesizer = SynthesizerAgent(llm_client)

    async def run(self, request: AnalyzeTickerRequest, correlation_id: str) -> AnalysisResult:
        """
        Executes the analysis workflow.

        The workflow proceeds in three main stages:
        1.  **Planning**: The PlannerAgent determines the necessary analysis steps.
        2.  **Data Collection & Analysis**: Specialized agents run in parallel to
            gather and analyze fundamentals, share price data, and valuation.
        3.  **Synthesis**: The SynthesizerAgent combines all the intermediate
            analyses into a final, comprehensive report and verdict.
        """
        try:
            # Stage 1: Planning
            plan = await self._planner.create_plan(request)

            # Stage 2: Parallel Data Collection & Analysis
            tasks = {
                "fundamentals": self._fundamentals.analyze(plan),
                "share_price": self._share_price.analyze(plan),
                "valuation": self._valuation.analyze(plan),
                "news": self._news.analyze_news(plan.ticker),
            }
            results = await asyncio.gather(*tasks.values(), return_exceptions=True)
            context: Dict[str, Any] = dict(zip(tasks.keys(), results))
            context["plan"] = plan

            # Check for errors in parallel tasks
            for task_name, result in context.items():
                if isinstance(result, Exception):
                    logger.error(
                        f"Error in task '{task_name}' for ticker {plan.ticker}: {result}",
                        extra={"cid": correlation_id},
                    )
                    # Replace error with a placeholder for the synthesizer
                    context[task_name] = f"Error: Analysis for {task_name} failed."

            # Stage 3: Synthesis
            final_result = await self._synthesizer.synthesize(context)
            final_result.correlation_id = correlation_id
            return final_result

        except Exception as e:
            logger.exception(
                f"Workflow failed for ticker {request.ticker}: {e}",
                extra={"cid": correlation_id},
            )
            return AnalysisResult(
                correlation_id=correlation_id,
                ticker=request.ticker,
                market=request.market,
                status="failed",
                error=str(e),
            )
