"""Event model for Data File Ready notifications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DatasetType = Literal[
    "company",
    "share_price",
    "balance_sheet",
    "income_statement",
    "cash_flow_statement",
    "insider_transaction",
    "ticker_document",
]

class DataFileStatus(BaseModel):
    ticker: str
    market: str
    source: str
    file_type: str
    latest_processed_date: Optional[str] = None
    status: Literal["COMPLETED", "FAILED"]
    extraction_status: Optional[Literal["FULL", "PARTIAL", "EMPTY"]] = None
    message: Optional[str] = None

class DataFileReadyEvent(BaseModel):
    """Notification that a dataset has been extracted and saved to a shared Parquet file."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: str = "oraculum.data_file_ready"
    dataset: DatasetType
    path: str
    template: Optional[str] = None
    variant: Optional[str] = None
    schema_version: int = 1
    run_id: str
    file_checksum: str
    record_count: int
    file_statuses: list[DataFileStatus] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=_utcnow)
