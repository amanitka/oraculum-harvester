"""SQLModel view definition for on-demand derived metrics."""

from __future__ import annotations

from datetime import date

from sqlmodel import Field, SQLModel


class DerivedMetricsDB(SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Read-only row mapped to the `v_derived_metrics` database view."""

    __tablename__ = "v_derived_metrics"
    __table_args__ = {"info": {"is_view": True}}

    composite_key: str = Field(primary_key=True)
    ticker: str
    simfin_id: int
    currency: str
    template: str
    variant: str
    fiscal_year: int
    fiscal_period: str
    report_date: date
    publish_date: date
    restated_date: date | None = None
    ebitda: float | None = None
    free_cash_flow: float | None = None
    ncav: float | None = None
    net_net_working_capital: float | None = None
    shares_stabilized: float | None = None
    return_on_equity: float | None = None
    net_margin: float | None = None
    revenue: float | None = None
    net_income: float | None = None
