"""SQLModel table definition for ingestion run logs."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IngestionRunLogDB(SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Log of processed Parquet data file ready events to enforce idempotency."""

    __tablename__ = "t_ingestion_run_log"
    __table_args__ = (
        UniqueConstraint(
            "dataset", "run_id", "file_checksum", name="uq_run_log_idempotency"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    dataset: str = Field(index=True)
    run_id: str = Field(index=True)
    file_checksum: str

    status: str = Field(description="SUCCESS or FAILED")
    loaded_rows: int = Field(default=0)
    merged_rows: int = Field(default=0)
    duration_ms: int = Field(default=0)
    error_text: Optional[str] = None

    created_at: datetime = Field(default_factory=_utcnow)
