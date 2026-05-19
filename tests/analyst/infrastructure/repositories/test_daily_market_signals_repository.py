"""Tests for daily market signals repository queries."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, cast

from sqlalchemy.dialects import postgresql

from analyst.infrastructure.models.daily_market_signals import DailyMarketSignalDB
from analyst.infrastructure.repositories.daily_market_signals import (
    DailyMarketSignalsQuery,
    DailyMarketSignalsRepository,
)


class _Result:
    def __init__(self, rows: list[DailyMarketSignalDB]) -> None:
        self._rows = rows

    def all(self) -> list[DailyMarketSignalDB]:
        return self._rows


class _Session:
    def __init__(self, rows: list[DailyMarketSignalDB]) -> None:
        self.rows = rows
        self.calls: list[Any] = []

    async def exec(
        self,
        statement: Any,
    ) -> _Result:
        self.calls.append(statement)
        return _Result(self.rows)


def test_daily_market_signals_repository_builds_parameterized_filtered_query() -> None:
    """Ensure ticker, market, date range, and month-end filters are parameterized."""
    session = _Session([_signal_row()])
    repository = DailyMarketSignalsRepository(cast(Any, session))
    query = DailyMarketSignalsQuery(
        ticker=" aapl ",
        market=" US ",
        from_date=date(2026, 1, 1),
        to_date=date(2026, 1, 31),
        only_month_end=True,
    )

    rows = asyncio.run(repository.fetch(query))

    statement = session.calls[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "FROM v_daily_market_signals" in sql
    assert "v_daily_market_signals.ticker = %(ticker_1)s" in sql
    assert "v_daily_market_signals.market = %(market_1)s" in sql
    assert "v_daily_market_signals.trade_date >= %(trade_date_1)s" in sql
    assert "v_daily_market_signals.trade_date <= %(trade_date_2)s" in sql
    assert "v_daily_market_signals.flag_last_day_of_month = %(flag_last_day_of_month_1)s" in sql
    assert compiled.params["ticker_1"] == "AAPL"
    assert compiled.params["market_1"] == "us"
    assert compiled.params["trade_date_1"] == date(2026, 1, 1)
    assert compiled.params["trade_date_2"] == date(2026, 1, 31)
    assert compiled.params["flag_last_day_of_month_1"] == "Y"
    assert rows[0].ticker == "AAPL"
    assert rows[0].is_graham_net_net == 1


def test_daily_market_signals_repository_supports_unfiltered_query() -> None:
    """Ensure unfiltered query only applies ordering and pagination."""
    session = _Session([])
    repository = DailyMarketSignalsRepository(cast(Any, session))
    query = DailyMarketSignalsQuery(ticker=None, market=None, limit=100, offset=200)

    rows = asyncio.run(repository.fetch(query))

    statement = session.calls[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert rows == []
    assert "v_daily_market_signals.ticker =" not in sql
    assert "v_daily_market_signals.market =" not in sql
    assert "v_daily_market_signals.flag_last_day_of_month =" not in sql
    assert compiled.params == {"param_1": 100, "param_2": 200}


def test_daily_market_signals_model_maps_read_only_view() -> None:
    """Ensure daily market signals use an ORM model mapped to the SQL view."""
    assert DailyMarketSignalDB.__tablename__ == "v_daily_market_signals"
    assert DailyMarketSignalDB.__table__.info["is_view"] is True
    assert [column.name for column in DailyMarketSignalDB.__table__.primary_key] == [
        "trade_date",
        "ticker",
        "market",
    ]


def _signal_row() -> DailyMarketSignalDB:
    return DailyMarketSignalDB(
        trade_date=date(2026, 1, 31),
        ticker="AAPL",
        market="us",
        flag_last_day_of_month="Y",
        share_price=210.0,
        volume=101_000,
        active_fiscal_year=2025,
        active_fiscal_period="TTM",
        market_capitalization=3_100_000_000_000.0,
        is_graham_net_net=1,
        return_on_equity=0.32,
    )
