"""SQLModel view definition for daily market signals."""

from __future__ import annotations

from datetime import date

from sqlmodel import Field, SQLModel


class DailyMarketSignalDB(SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Read-only row mapped to the `v_daily_market_signals` database view."""

    __tablename__ = "v_daily_market_signals"
    __table_args__ = {"info": {"is_view": True}}

    trade_date: date = Field(primary_key=True)
    ticker: str = Field(primary_key=True)
    market: str = Field(primary_key=True)

    flag_last_day_of_month: str
    currency: str | None = None
    share_price: float | None = None
    volume: int | None = None

    pct_from_50d_ma: float | None = None
    pct_from_200d_ma: float | None = None
    volume_velocity: float | None = None

    active_fiscal_year: int | None = None
    active_fiscal_period: str | None = None
    active_report_publish_date: date | None = None

    market_capitalization: float | None = None
    pe_ratio: float | None = None
    earnings_yield: float | None = None
    price_to_fcf: float | None = None
    price_to_sales: float | None = None
    price_to_book: float | None = None
    price_to_ncav: float | None = None
    price_to_nnwc: float | None = None
    is_graham_net_net: int
    enterprise_value: float | None = None
    enterprise_value_to_ebitda: float | None = None

    return_on_capital_employed: float | None = None
    return_on_equity: float | None = None
    net_margin: float | None = None
    current_ratio: float | None = None
    debt_to_equity: float | None = None
