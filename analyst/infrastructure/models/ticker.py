"""SQLModel table definition for persisted ticker metadata."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint

from analyst.infrastructure.models.base import AuditMixin
from sqlalchemy import BigInteger, Column

class TickerDB(AuditMixin, SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Persistent row backing the `ticker` Kafka topic."""

    __tablename__ = "t_ticker"
    __table_args__ = (
        UniqueConstraint("ticker", "market", name="uq_ticker_ticker_market"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    ticker: str = Field(index=True)
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    company_name: str

    # Financial metadata
    industry_id: Optional[str] = None
    industry_name: Optional[str] = None
    sector_name: Optional[str] = None
    isin: Optional[str] = None
    description: Optional[str] = None
    employee_count: Optional[int] = Field(sa_column=Column(BigInteger))

    # Location / identity
    market: str = Field(default="us")
    currency: str = Field(default="USD")
    cik: Optional[str] = None

    extracted_at: datetime
