from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session
from sqlmodel import select

from analyst.application.analysis.models import AnalysisResult, AnalysisStatus
from analyst.infrastructure.models.analysis import AnalysisDB


class AnalysisRepository:
    """
    Provides data access methods for reading and writing analysis results
    to the `t_analysis` table.
    """

    def __init__(self, session: Session):
        self._session = session

    def insert_pending(self, correlation_id: UUID, ticker: str, market: str, analysis_date: datetime.date) -> None:
        """Create a new analysis record in 'pending' state."""
        now = datetime.now(timezone.utc)
        analysis_db = AnalysisDB(
            correlation_id=correlation_id,
            ticker=ticker,
            market=market,
            analysis_date=analysis_date,
            status="pending",
            created_at=now,
            updated_at=now,
        )
        self._session.add(analysis_db)
        self._session.flush()

    def _get_db_by_correlation_id(self, correlation_id: UUID) -> AnalysisDB | None:
        """Fetch a single analysis record by its correlation ID."""
        statement = select(AnalysisDB).where(AnalysisDB.correlation_id == correlation_id)
        return self._session.exec(statement).one_or_none()

    def mark_running(self, correlation_id: UUID) -> None:
        """Update the status of an analysis to 'running'."""
        analysis_db = self._get_db_by_correlation_id(correlation_id)
        if analysis_db:
            analysis_db.status = "running"
            analysis_db.updated_at = datetime.now(timezone.utc)
            self._session.flush()

    def mark_completed(self, result: AnalysisResult) -> None:
        """Update a record to 'completed' and store the final analysis payload."""
        analysis_db = self._get_db_by_correlation_id(result.correlation_id)
        if analysis_db:
            analysis_db.status = "completed"
            analysis_db.report_md = result.report_md
            analysis_db.verdict = result.verdict
            analysis_db.conviction = result.conviction
            analysis_db.payload = {
                "key_drivers": result.key_drivers,
                "key_risks": result.key_risks,
                "agent_trace": result.agent_trace,
                "token_usage": result.token_usage,
            }
            analysis_db.updated_at = datetime.now(timezone.utc)
            self._session.flush()

    def mark_failed(self, correlation_id: UUID, error_message: str) -> None:
        """Update a record to 'failed' and store the error message."""
        analysis_db = self._get_db_by_correlation_id(correlation_id)
        if analysis_db:
            analysis_db.status = "failed"
            analysis_db.error = error_message
            analysis_db.updated_at = datetime.now(timezone.utc)
            self._session.flush()

    def get_by_correlation_id(self, correlation_id: UUID) -> AnalysisDB | None:
        """Retrieve a single analysis record by its correlation ID."""
        return self._get_db_by_correlation_id(correlation_id)

    def list_recent(self, limit: int = 20, offset: int = 0) -> list[AnalysisDB]:
        """List recent analyses, sorted by creation date descending."""
        statement = select(AnalysisDB).order_by(AnalysisDB.created_at.desc()).limit(limit).offset(offset)
        return self._session.exec(statement).all()

    def list_by_ticker(self, ticker: str, market: str = "us", limit: int = 20) -> list[AnalysisDB]:
        """List recent analyses for a specific ticker, sorted by creation date."""
        statement = (
            select(AnalysisDB)
            .where(AnalysisDB.ticker == ticker, AnalysisDB.market == market)
            .order_by(AnalysisDB.created_at.desc())
            .limit(limit)
        )
        return self._session.exec(statement).all()

    def list_by_status(self, status: AnalysisStatus, limit: int = 100) -> list[AnalysisDB]:
        """List analyses currently in a specific status."""
        statement = select(AnalysisDB).where(AnalysisDB.status == status).order_by(AnalysisDB.created_at.asc()).limit(limit)
        return self._session.exec(statement).all()
