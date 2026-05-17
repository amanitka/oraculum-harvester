import logging
from datetime import date, datetime, timezone
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.orm import Session

from analyst.application.analysis.models import AnalysisResult
from analyst.infrastructure.repositories.analysis import AnalysisRepository
from common.requests.analyze_ticker import AnalyzeTickerRequest

logger = logging.getLogger(__name__)


def run_workflow_stub(request: AnalyzeTickerRequest, correlation_id: UUID) -> AnalysisResult:
    """
    A stubbed implementation of the analysis workflow.

    This function returns a fixed markdown string to prove the end-to-end
    wiring of the command path before introducing real LLM calls.
    """
    logger.info(f"Running stubbed analysis workflow for {request.ticker}", extra={"cid": correlation_id})
    now = datetime.now(timezone.utc)
    analysis_date = request.as_of or date.today()

    return AnalysisResult(
        correlation_id=correlation_id,
        ticker=request.ticker,
        market=request.market,
        analysis_date=analysis_date,
        status="completed",
        report_md="# Stubbed Analysis Report\n\nThis is a placeholder report.",
        verdict="neutral",
        conviction=3,
        key_drivers=["Stubbed driver 1"],
        key_risks=["Stubbed risk 1"],
        agent_trace={"stub": "trace"},
        token_usage=0,
        created_at=now,  # Note: The repository will set the definitive timestamps.
        updated_at=now,
    )


def handle_analyze_ticker_request(session: Session, request_data: dict, correlation_id: UUID) -> None:
    """
    Handles an incoming request to analyze a ticker.

    This function orchestrates the analysis lifecycle:
    1. Inserts a 'pending' record into the database.
    2. Marks the record as 'running'.
    3. Executes the analysis workflow (currently a stub).
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
        result = run_workflow_stub(request, correlation_id)

        # 4. Mark as completed
        repo.mark_completed(result)
        session.commit()

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
