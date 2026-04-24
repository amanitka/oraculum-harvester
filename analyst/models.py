from datetime import datetime, timezone
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint


class TickerDB(SQLModel, table=True):  # type: ignore[call-arg,misc]  # type: ignore[call-arg,misc]
    __tablename__ = "ticker"
    __table_args__ = (
        UniqueConstraint("symbol", "market", name="uq_ticker_symbol_market"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    symbol: str = Field(index=True)
    provider_id: Optional[str] = None
    provider_name: Optional[str] = None
    company_name: str

    # Financial Metadata
    industry_id: Optional[str] = None
    industry_name: Optional[str] = None
    sector_name: Optional[str] = None
    isin: Optional[str] = None
    description: Optional[str] = None
    employee_count: Optional[int] = None

    # Location/Identity
    market: str = Field(default="us")
    currency: str = Field(default="USD")
    cik: Optional[str] = None

    extracted_at: datetime

    # Audit fields
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
