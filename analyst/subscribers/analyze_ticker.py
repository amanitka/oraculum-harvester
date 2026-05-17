import logging
from datetime import date, datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from analyst.application.agents.context_factory import AgentContextFactory
from analyst.application.analysis.models import AnalysisResult
from analyst.application.analysis.workflow import AnalysisWorkflow
from analyst.infrastructure.repositories.analysis import AnalysisRepository
from common.llm.litellm_client import LiteLlmClient
from common.requests.analyze_ticker import AnalyzeTickerRequest

logger = logging.getLogger(__name__)


def handle_analyze_ticker_request(session: Session, request_data: dict, correlation_id: UUID) -> None:
    """
    Handles an incoming request to analyze a ticker.

    This function orchestrates the analysis lifecycle:
    1. Inserts a 'pending' record into the database.
    2. Marks the record as 'running'.
    3. Executes the multi-agent analysis workflow.
    4. Marks the record as 'completed' or 'failed'.
    """
    try:
        request = AnalyzeTickerRequest.model_validate(request_data)
    except ValidationError as e:
        logger.error(f"Failed to validate AnalyzeTickerRequest: {e}", extra={"cid": correlation_id})
        return

    repo = AnalysisRepository(session)
    logger.info(
        f"Handling ticker analysis request for {request.ticker}",
        extra={"cid": correlation_id, "ticker": request.ticker},
    )

    try:
        # 1. Insert pending record
        repo.insert_pending(
            correlation_id=correlation_id,
            ticker=request.ticker,
            market=request.market,
            analysis_date=request.as_of or date.today(),
        )
        session.commit()

        # 2. Mark as running
        repo.mark_running(correlation_id)
        session.commit()

        # 3. Run workflow
        llm_client = LiteLlmClient()
        tools = AgentContextFactory(session).create_tools()
        workflow = AnalysisWorkflow(llm_client, tools)

        # The workflow expects to be run in an async context.
        # Since this subscriber function is synchronous (based on FastStream setup likely),
        # we need to use asyncio.run to execute the async workflow.
        import asyncio
        result = asyncio.run(workflow.run(request, correlation_id))

        # 4. Mark as completed or failed based on workflow result
        if result.status == "failed":
             repo.mark_failed(correlation_id, result.error or "Unknown workflow error")
        else:
            repo.mark_completed(result)
        
        session.commit()

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
        repo.mark_failed(correlation_id, str(e))
        session.commit()
