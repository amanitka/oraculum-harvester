"""Event model for Data File Ready notifications."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


DatasetType = Literal[
    "ticker",
    "share_price",
    "balance_sheet",
    "income_statement",
    "cash_flow_statement",
]


class DataFileReadyEvent(BaseModel):
    """Notification that a dataset has been extracted and saved to a shared Parquet file."""

    model_config = ConfigDict(populate_by_name=True)

    event_type: Literal["simfin.data_file_ready"] = "simfin.data_file_ready"
    dataset: DatasetType
    path: str
    template: Optional[str] = None
    variant: Optional[str] = None
    schema_version: int = 1
    run_id: str
    file_checksum: str
    record_count: int
    created_at: datetime = Field(default_factory=_utcnow)
