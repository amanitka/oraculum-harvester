import logging
import time
from datetime import datetime, timezone
from uuid import UUID

from analyst.application.agents.cash_flow import CashFlowAgent
from analyst.application.agents.context import AgentContext
from analyst.application.agents.critic import CriticAgent
from analyst.application.agents.factsheet import FactSheetAgent
from analyst.application.agents.fundamentals import FundamentalsAgent
from analyst.application.agents.planner import PlannerAgent
from analyst.application.agents.risk import RiskAgent
from analyst.application.agents.share_price import SharePriceAgent
from analyst.application.agents.synthesizer import SynthesizerAgent
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
        self._fact_sheet_agent = FactSheetAgent()
        self._specialists = [
            FundamentalsAgent(),
            CashFlowAgent(),
            ValuationAgent(),
            RiskAgent(),
            SharePriceAgent(),
        ]
        self._critic = CriticAgent()
        self._synthesizer = SynthesizerAgent()

    async def run(self, request: AnalyzeTickerRequest, correlation_id: UUID) -> AnalysisResult:
        """
        Executes the analysis workflow for the given request.
        """
        start_time = time.monotonic()
        total_tokens = 0
        agent_trace = {}
        now = datetime.now(timezone.utc)
        
        cid = {"cid": correlation_id}
        logger.info(
            "Starting analysis workflow for ticker %s", request.ticker, extra=cid
        )

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
            logger.info("Starting Planner phase", extra=cid)
            plan_out = await self._planner.run(initial_ctx)
            plan = plan_out.result
            total_tokens += plan_out.tokens
            agent_trace["Planner"] = plan.model_dump()
            logger.info(
                "Planner phase complete. Tokens: %d. Plan: %s",
                plan_out.tokens,
                plan.model_dump_json(),
                extra=cid,
            )

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

            logger.info("Starting FactSheet phase", extra=cid)
            fact_sheet_out = await self._fact_sheet_agent.run(shared_ctx)
            total_tokens += fact_sheet_out.tokens
            shared_ctx.prior_outputs["FactSheet"] = fact_sheet_out.result
            logger.info("FactSheet phase complete.", extra=cid)

            for agent in self._specialists:
                logger.info(f"Starting {agent.name} phase", extra=cid)
                output = await agent.run(shared_ctx)
                shared_ctx.prior_outputs[agent.name] = output.result
                total_tokens += output.tokens
                agent_trace[agent.name] = output.result.model_dump()
                logger.info(
                    "%s phase complete. Tokens: %d",
                    agent.name,
                    output.tokens,
                    extra=cid,
                )

            logger.info("Starting Critic phase", extra=cid)
            critic_output = await self._critic.run(shared_ctx)
            shared_ctx.prior_outputs["Critic"] = critic_output.result
            total_tokens += critic_output.tokens
            agent_trace["Critic"] = critic_output.result.model_dump()
            logger.info(
                "Critic phase complete. Tokens: %d. Consistent: %s",
                critic_output.tokens,
                critic_output.result.is_consistent,
                extra=cid,
            )

            logger.info("Starting Synthesizer phase", extra=cid)
            final_output = await self._synthesizer.run(shared_ctx)
            total_tokens += final_output.tokens
            agent_trace["Synthesizer"] = final_output.result.model_dump()
            logger.info(
                "Synthesizer phase complete. Tokens: %d. Verdict: %s",
                final_output.tokens,
                final_output.result.verdict,
                extra=cid,
            )

            elapsed_s = time.monotonic() - start_time
            logger.info(
                "Analysis workflow completed successfully in %.2f seconds. Total tokens: %d",
                elapsed_s,
                total_tokens,
                extra=cid,
            )

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
            elapsed_s = time.monotonic() - start_time
            logger.exception(
                "Workflow failed after %.2f seconds: %s", elapsed_s, e, extra=cid
            )
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
