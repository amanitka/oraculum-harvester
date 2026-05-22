"""SQLModel table definition for persisted share price snapshots."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint
from sqlalchemy import BigInteger, Column

from analyst.infrastructure.models.base import AuditMixin


class SharePriceDB(AuditMixin, SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Persistent row backing the `share_price` Kafka topic."""

    __tablename__ = "t_share_price"
    __table_args__ = (UniqueConstraint("ticker", "market", "trade_date", name="uq_share_price_composite"),)

    # Note: t_share_price is a partitioned table in Postgres, and we don't use
    # an autoincrement ID since the primary key is composite. We map the columns
    # directly here for ORM read queries (though inserts use raw SQL for speed).
    ticker: str = Field(primary_key=True)
    market: str = Field(primary_key=True)
    trade_date: date = Field(primary_key=True)

    sim_fin_id: Optional[int] = None
    currency: Optional[str] = None

    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    adj_close: Optional[float] = None

    volume: Optional[int] = Field(default=None, sa_column=Column(BigInteger()))
    shares_outstanding: Optional[int] = Field(default=None, sa_column=Column(BigInteger()))
    dividend: Optional[float] = None

    extracted_at: datetime
