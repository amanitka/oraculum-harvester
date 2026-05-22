"""Tests for on-demand derived metrics repository queries."""

from __future__ import annotations

import asyncio
from datetime import date
from typing import Any, cast

from sqlalchemy.dialects import postgresql

from analyst.infrastructure.models.derived_metrics import DerivedMetricsDB
from analyst.infrastructure.repositories.derived_metrics import (
    DerivedMetricsQuery,
    DerivedMetricsRepository,
)


class _Result:
    def __init__(self, rows: list[DerivedMetricsDB]) -> None:
        self._rows = rows

    def all(self) -> list[DerivedMetricsDB]:
        return self._rows


class _Session:
    def __init__(self, rows: list[DerivedMetricsDB]) -> None:
        self.rows = rows
        self.calls: list[Any] = []

    async def exec(
        self,
        statement: Any,
    ) -> _Result:
        self.calls.append(statement)
        return _Result(self.rows)


def test_derived_metrics_repository_builds_parameterized_filtered_query() -> None:
    """Ensure ticker, template, and variant filters are passed as parameters."""
    session = _Session([_derived_metrics_row()])
    repository = DerivedMetricsRepository(cast(Any, session))
    query = DerivedMetricsQuery(ticker=" aapl ", template="GENERAL", variant="TTM")

    rows = asyncio.run(repository.fetch(query))

    statement = session.calls[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert "FROM v_derived_metrics" in sql
    assert "v_derived_metrics.ticker = %(ticker_1)s" in sql
    assert "v_derived_metrics.template = %(template_1)s" in sql
    assert "v_derived_metrics.variant = %(variant_1)s" in sql
    assert compiled.params == {
        "param_1": 500,
        "param_2": 0,
        "ticker_1": "AAPL",
        "template_1": "general",
        "variant_1": "ttm",
    }
    assert rows[0].ticker == "AAPL"
    assert rows[0].return_on_equity == 0.2


def test_derived_metrics_repository_supports_all_tickers_query() -> None:
    """Ensure omitting ticker does not add a ticker filter."""
    session = _Session([])
    repository = DerivedMetricsRepository(cast(Any, session))
    query = DerivedMetricsQuery(template=None, limit=100, offset=200)

    rows = asyncio.run(repository.fetch(query))

    statement = session.calls[0]
    compiled = statement.compile(dialect=postgresql.dialect())
    sql = str(compiled)
    assert rows == []
    assert "v_derived_metrics.ticker =" not in sql
    assert "v_derived_metrics.template =" not in sql
    assert compiled.params == {"param_1": 100, "param_2": 200}


def test_derived_metrics_model_maps_read_only_view() -> None:
    """Ensure derived metrics use an ORM model mapped to the SQL view."""
    assert DerivedMetricsDB.__tablename__ == "v_derived_metrics"
    assert DerivedMetricsDB.__table__.info["is_view"] is True
    assert [column.name for column in DerivedMetricsDB.__table__.primary_key] == ["composite_key"]


def _derived_metrics_row() -> DerivedMetricsDB:
    return DerivedMetricsDB(
        composite_key="AAPL-2025-TTM-general-ttm",
        ticker="AAPL",
        simfin_id=111,
        currency="USD",
        template="general",
        variant="ttm",
        fiscal_year=2025,
        fiscal_period="TTM",
        report_date=date(2025, 12, 31),
        publish_date=date(2026, 1, 31),
        restated_date=None,
        ebitda=10.0,
        free_cash_flow=8.0,
        ncav=7.0,
        net_net_working_capital=6.0,
        shares_stabilized=5.0,
        return_on_equity=0.2,
        net_margin=0.1,
        revenue=100.0,
        net_income=10.0,
    )
