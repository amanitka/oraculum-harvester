from uuid import UUID

from sqlalchemy.orm import Session
from sqlmodel import select, func

from analyst.infrastructure.models.analysis import AnalysisDB


class AnalysisRepository:
    """
    Read-only repository for the UI to fetch analysis results from the database.
    """

    def __init__(self, session: Session):
        self._session = session

    def get_by_correlation_id(self, correlation_id: UUID) -> AnalysisDB | None:
        """Retrieve a single analysis by its correlation ID."""
        statement = select(AnalysisDB).where(AnalysisDB.correlation_id == correlation_id)
        return self._session.execute(statement).scalar_one_or_none()

    def list_recent(self, limit: int = 50, offset: int = 0) -> list[AnalysisDB]:
        """List all analyses, sorted by creation date descending."""
        statement = select(AnalysisDB).order_by(AnalysisDB.created_at.desc()).limit(limit).offset(offset)
        results = self._session.execute(statement).scalars().all()
        return results

    def get_running_count(self) -> int:
        """Return the number of analyses currently in 'pending' or 'running' state."""
        statement = select(func.count()).select_from(AnalysisDB).where(AnalysisDB.status.in_(["pending", "running"]))
        count = self._session.execute(statement).scalar_one()
        return count
