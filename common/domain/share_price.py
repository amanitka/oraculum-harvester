"""Share price domain model."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Optional

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SharePrice(BaseModel):
    """A single daily share price observation from SimFin."""

    model_config = ConfigDict(populate_by_name=True)

    ticker: str = Field(alias="Ticker")
    sim_fin_id: Optional[int] = Field(None, alias="SimFinId")
    currency: Optional[str] = Field(None, alias="Currency")
    market: str
    trade_date: date = Field(alias="Date")
    open: Optional[float] = Field(None, alias="Open")
    high: Optional[float] = Field(None, alias="High")
    low: Optional[float] = Field(None, alias="Low")
    close: Optional[float] = Field(None, alias="Close")
    adj_close: Optional[float] = Field(None, alias="Adj. Close")
    volume: Optional[int] = Field(None, alias="Volume")
    shares_outstanding: Optional[int] = Field(None, alias="Shares Outstanding (Common)")
    dividend: Optional[float] = Field(None, alias="Dividend")
    extracted_at: datetime = Field(default_factory=_utcnow)

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_missing(cls, v: Any) -> Any:
        """Turn pandas NaN/NaT and empty strings into ``None`` for every field."""
        if v is None:
            return None
        if isinstance(v, str):
            return v if v.strip() else None
        try:
            if pd.isna(v):
                return None
        except TypeError, ValueError:
            pass
        return v

    @field_validator("trade_date", mode="before")
    @classmethod
    def _parse_date(cls, v: Any) -> Any:
        """Coerce string and pd.Timestamp to ``date``."""
        if isinstance(v, str):
            return date.fromisoformat(v)
        if hasattr(v, "date") and callable(v.date):
            return v.date()
        return v


class SharePriceBatch(BaseModel):
    """A batch of share price rows published as a single Kafka message."""

    market: str
    from_date: Optional[date] = None
    rows: list[SharePrice]
    extracted_at: datetime = Field(default_factory=_utcnow)
