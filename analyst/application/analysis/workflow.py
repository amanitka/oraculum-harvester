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
from analyst.application.agents.tools import DataTools
from analyst.application.agents.valuation import ValuationAgent
from analyst.application.analysis.models import AnalysisResult
from common.llm.base import LlmClient
from common.requests.analyze_ticker import AnalyzeTickerRequest

logger = logging.getLogger(__name__)


class AnalysisWorkflow:
    """
    Orchestrates the multi-agent execution pipeline.
    """

    def __init__(self, llm_client: LlmClient, tools: DataTools):
        self._llm = llm_client
        self._tools = tools

        # Roster
        self._planner = PlannerAgent()
        self._specialists = [
            FundamentalsAgent(),
            CashFlowAgent(),
            ValuationAgent(),
            RiskAgent(),
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
        
        # We need an initial context just to run the planner.
        # The planner will dictate the template and variants.
        # For the very first step, we don't know the template yet.
        initial_ctx = AgentContext(
            ticker=request.ticker,
            market=request.market,
            as_of=request.as_of or now.date(),
            template="general", # Dummy placeholder, planner will resolve the real one
            default_variant=request.default_variant,
            tools=self._tools,
            llm=self._llm,
            token_budget=100000, # Example hard budget
            prior_outputs={},
        )

        try:
            # 1. Planner Phase
            logger.info("Starting Planner phase", extra={"cid": correlation_id})
            plan = await self._planner.run(initial_ctx)
            
            # TODO: Track tokens from the planner response if we can extract it cleanly.
            # Currently the Agent run method just returns the parsed Pydantic model.
            # To get tokens, we'd need the Agent to return a wrapper or access the raw response.
            # For simplicity in this implementation, we'll omit token tracking here, 
            # or it requires refactoring the Agent.run signature.
            # Let's assume we capture it via some side-channel or log parsing later,
            # or we update the Agent base class to return (Output, TokenUsage).
            
            agent_trace["Planner"] = plan.model_dump()
            
            # Rebuild context with the resolved template from the planner
            shared_ctx = AgentContext(
                ticker=request.ticker,
                market=request.market,
                as_of=initial_ctx.as_of,
                template=plan.template,
                default_variant=request.default_variant,
                tools=self._tools,
                llm=self._llm,
                token_budget=100000,
                prior_outputs={},
            )

            # 2. Specialist Phase (Sequential execution)
            for agent in self._specialists:
                logger.info(f"Starting {agent.name} phase", extra={"cid": correlation_id})
                
                # In a more advanced implementation, we would inject the specific variant 
                # chosen by the planner for this specialist.
                # For example, modifying the context before passing it, or the agent reads the plan.
                # We'll just pass the shared context for now as per the simplified agent implementations.
                
                output = await agent.run(shared_ctx)
                shared_ctx.prior_outputs[agent.name] = output
                agent_trace[agent.name] = output.model_dump()

            # 3. Synthesizer Phase
            logger.info("Starting Synthesizer phase", extra={"cid": correlation_id})
            final_output = await self._synthesizer.run(shared_ctx)
            agent_trace["Synthesizer"] = final_output.model_dump()

            # Construct the final result
            return AnalysisResult(
                correlation_id=correlation_id,
                ticker=request.ticker,
                market=request.market,
                analysis_date=shared_ctx.as_of,
                status="completed",
                report_md=final_output.report_md,
                verdict=final_output.verdict,
                conviction=final_output.conviction,
                key_drivers=final_output.key_drivers,
                key_risks=final_output.key_risks,
                agent_trace=agent_trace,
                token_usage=total_tokens, # We'd need to aggregate this properly
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
                created_at=now,
                updated_at=datetime.now(timezone.utc),
            )
