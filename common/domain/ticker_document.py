"""Domain model for SEC Ticker Documents."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TickerDocument(BaseModel):
    """Represent a document extracted from SEC EDGAR (e.g. 8-K EX99_1, 10-K Risk Factors, etc.)."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    ticker: str
    market: str
    source: str
    document_type: str
    document_subtype: str
    accession_number: str
    source_url: str
    report_period: date | None = Field(default=None)
    filing_date: date | None = Field(default=None)
    content: str
    extracted_at: datetime = Field(default_factory=_utcnow)

    @field_validator("report_period", "filing_date", mode="before")
    @classmethod
    def _parse_dates(cls, v: Any) -> Any:
        if not v:
            return None
        if isinstance(v, str):
            try:
                return date.fromisoformat(v[:10])
            except ValueError:
                return None
        if isinstance(v, datetime):
            return v.date()
        return v
