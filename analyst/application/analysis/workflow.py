import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from analyst.application.agents.cash_flow import CashFlowAgent
from analyst.application.agents.context import AgentContext
from analyst.application.agents.fundamentals import FundamentalsAgent
from analyst.application.agents.planner import PlannerAgent
from analyst.application.agents.risk import RiskAgent
from analyst.application.agents.synthesizer import SynthesizerAgent
from analyst.application.agents.share_price_signals import SharePriceSignalsAgent
from analyst.application.agents.tools import DataTools
from analyst.application.agents.valuation import ValuationAgent
from analyst.application.analysis.models import AnalysisResult
from common.config import config
from common.llm.base import LlmClient
from common.requests.analyze_ticker import AnalyzeTickerRequest
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)


class AnalysisWorkflow:
    """
    Orchestrates the multi-agent execution pipeline.
    """

    def __init__(self, llm_client: LlmClient, tools: DataTools):
        self._llm = llm_client
        self._tools = tools

        self._planner = PlannerAgent()
        self._specialists = [
            FundamentalsAgent(),
            CashFlowAgent(),
            ValuationAgent(),
            RiskAgent(),
            SharePriceSignalsAgent(),
        ]
        self._synthesizer = SynthesizerAgent()

    async def run(self, request: AnalyzeTickerRequest, correlation_id: UUID) -> AnalysisResult:
        """
        Executes the analysis workflow for the given request.
        """
        start_time = time.monotonic()
        total_tokens = 0
        agent_trace = {}
        now = datetime.now(timezone.utc)
        
        initial_ctx = AgentContext(
            ticker=request.ticker,
            market=request.market,
            as_of=request.as_of or now.date(),
            template="general",
            default_variant=request.default_variant,
            tools=self._tools,
            llm=self._llm,
            token_budget=config.llm.workflow_token_budget,
            prior_outputs={},
        )

        try:
            logger.info("Starting Planner phase", extra={"cid": correlation_id})
            plan_out = await self._planner.run(initial_ctx)
            plan = plan_out.result
            total_tokens += plan_out.tokens
            agent_trace["Planner"] = plan.model_dump()
            
            shared_ctx = AgentContext(
                ticker=request.ticker,
                market=request.market,
                as_of=initial_ctx.as_of,
                template=plan.template,
                default_variant=request.default_variant,
                tools=self._tools,
                llm=self._llm,
                token_budget=config.llm.workflow_token_budget,
                prior_outputs={},
            )

            for agent in self._specialists:
                logger.info(f"Starting {agent.name} phase", extra={"cid": correlation_id})
                
                output = await agent.run(shared_ctx)
                shared_ctx.prior_outputs[agent.name] = output.result
                total_tokens += output.tokens
                agent_trace[agent.name] = output.result.model_dump()

            logger.info("Starting Synthesizer phase", extra={"cid": correlation_id})
            final_output = await self._synthesizer.run(shared_ctx)
            total_tokens += final_output.tokens
            agent_trace["Synthesizer"] = final_output.result.model_dump()

            return AnalysisResult(
                correlation_id=correlation_id,
                ticker=request.ticker,
                market=request.market,
                analysis_date=shared_ctx.as_of,
                status="completed",
                report_md=final_output.result.report_md,
                verdict=final_output.result.verdict,
                conviction=final_output.result.conviction,
                key_drivers=final_output.result.key_drivers,
                key_risks=final_output.result.key_risks,
                agent_trace=agent_trace,
                token_usage=total_tokens,
                created_at=now,
                updated_at=datetime.now(timezone.utc),
            )

        except Exception as e:
            logger.exception(f"Workflow failed: {e}", extra={"cid": correlation_id})
            return AnalysisResult(
                correlation_id=correlation_id,
                ticker=request.ticker,
                market=request.market,
                analysis_date=initial_ctx.as_of,
                status="failed",
                error=str(e),
                agent_trace=agent_trace,
                token_usage=total_tokens,
                created_at=now,
                updated_at=datetime.now(timezone.utc),
            )
