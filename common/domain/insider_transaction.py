"""Domain model for Insider Transactions."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class InsiderTransaction(BaseModel):
    """An insider transaction parsed from OpenInsider."""

    model_config = ConfigDict(populate_by_name=True)

    id: str
    trade_date: datetime | None = Field(default=None, alias="trade_date")
    filing_date: datetime
    ticker: str
    insider_name: str
    title: str | None = Field(default=None)
    trade_type: str
    price: float | None = Field(default=None)
    qty: float | None = Field(default=None)
    owned: float | None = Field(default=None)
    delta_own: float | None = Field(default=None)
    value: float | None = Field(default=None)
    currency: str = Field(default="USD")
    market: str = Field(default="US")
    extracted_at: datetime
