"""SQLModel table definition for persisted derived financial metrics."""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from sqlmodel import Field, SQLModel, UniqueConstraint

from analyst.infrastructure.models.base import AuditMixin


class DerivedDB(AuditMixin, SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Persistent row backing the `derived` parquet dataset."""

    __tablename__ = "t_derived"
    __table_args__ = (
        UniqueConstraint("composite_key", name="uq_derived_composite_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    composite_key: str = Field(index=True)
    ticker: str = Field(index=True)
    simfin_id: int = Field(index=True)
    template: str
    variant: str = Field(index=True)
    currency: str
    fiscal_year: int
    fiscal_period: str
    report_date: date
    publish_date: date
    restated_date: Optional[date] = None
    extracted_at: datetime

    ebitda: Optional[float] = None
    free_cash_flow: Optional[float] = None
    ncav: Optional[float] = None
    net_net_working_capital: Optional[float] = None
    shares_stabilized: Optional[float] = None
    return_on_equity: Optional[float] = None
    net_margin: Optional[float] = None
    revenue: Optional[float] = None
    net_income: Optional[float] = None
