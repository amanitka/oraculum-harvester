import logging
from datetime import date, datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session as DependsSession
from analyst.application.agents.context_factory import AgentContextFactory
from analyst.application.analysis.models import AnalysisResult
from analyst.application.analysis.workflow import AnalysisWorkflow
from analyst.infrastructure.repositories.analysis import AnalysisRepository
from common.config import config
from common.llm.litellm_client import LiteLlmClient
from common.requests.analyze_ticker import AnalyzeTickerRequest

logger = logging.getLogger(__name__)


@broker.subscriber(
    config.topics.analyst_request,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def handle_analyze_ticker_request(request: AnalyzeTickerRequest, session: AsyncSession = DependsSession()) -> None:
    """
    Handles an incoming request to analyze a ticker.

    This function orchestrates the analysis lifecycle:
    1. Inserts a 'pending' record into the database.
    2. Marks the record as 'running'.
    3. Executes the multi-agent analysis workflow.
    4. Marks the record as 'completed' or 'failed'.
    """
    correlation_id = request.correlation_id

    logger.info(
        f"Handling ticker analysis request for {request.ticker}",
        extra={"cid": correlation_id, "ticker": request.ticker},
    )

    try:
        # Use run_sync for the initial synchronous repository operations
        def _run_sync_repo_ops(sync_session):
            repo = AnalysisRepository(sync_session)
            repo.insert_pending(
                correlation_id=correlation_id,
                ticker=request.ticker,
                market=request.market,
                analysis_date=request.as_of or date.today(),
            )
            sync_session.commit()
            repo.mark_running(correlation_id)
            sync_session.commit()

        await session.run_sync(_run_sync_repo_ops)

        # Now, for the async workflow, we use the async session
        llm_client = LiteLlmClient()
        tools = AgentContextFactory(session).create_tools() # Pass the async session
        workflow = AnalysisWorkflow(llm_client, tools)
        result = await workflow.run(request, correlation_id)

        # Finalize with sync operations
        def _finalize(sync_session):
            repo = AnalysisRepository(sync_session)
            if result.status == "failed":
                repo.mark_failed(correlation_id, result.error or "Unknown workflow error")
            else:
                repo.mark_completed(result)
            sync_session.commit()

        await session.run_sync(_finalize)

        if result.status == "completed":
            logger.info(
                f"Successfully completed analysis for {request.ticker}",
                extra={"cid": correlation_id, "ticker": request.ticker},
            )

    except Exception as e:
        logger.exception(
            f"Analysis failed for {request.ticker}: {e}",
            extra={"cid": correlation_id, "ticker": request.ticker},
        )
        def _fail(sync_session):
             repo = AnalysisRepository(sync_session)
             repo.mark_failed(correlation_id, str(e))
             sync_session.commit()
             
        await session.run_sync(_fail)
