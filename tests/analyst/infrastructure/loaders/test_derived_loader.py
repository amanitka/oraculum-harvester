"""Tests for derived dataset parquet loader SQL."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.sql.elements import TextClause

from analyst.infrastructure.loaders.derived import DerivedStrategy
from analyst.infrastructure.loaders.factory import get_strategy


class _CapturingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, list[dict[str, Any]] | None]] = []

    async def exec(
        self, statement: Any, params: list[dict[str, Any]] | None = None
    ) -> None:
        self.calls.append((statement, params))


def _derived_record() -> dict[str, Any]:
    return {
        "composite_key": "ABC-2024-FY-general-ttm",
        "template": "general",
        "variant": "ttm",
        "ticker": "ABC",
        "simfin_id": 1,
        "currency": "USD",
        "fiscal_year": 2024,
        "fiscal_period": "FY",
        "report_date": "2024-12-31",
        "publish_date": "2025-02-01",
        "restated_date": None,
        "extracted_at": "2026-05-12T18:00:00Z",
        "ebitda": 123.0,
        "free_cash_flow": 35.0,
        "ncav": 80.0,
        "net_net_working_capital": 25.0,
        "shares_stabilized": 9.0,
        "return_on_equity": 2.0,
        "net_margin": 1.0,
        "revenue": 100.0,
        "net_income": 100.0,
    }


def _find_statement_with_params(
    session: _CapturingSession, records: list[dict[str, Any]]
) -> TextClause:
    for statement, params in session.calls:
        if params is records:
            assert isinstance(statement, TextClause)
            return statement
    raise AssertionError("derived loader did not execute a parameterized staging insert")


def test_factory_registers_derived_strategy() -> None:
    """Ensure parquet loader dispatch can resolve the derived dataset."""
    assert isinstance(get_strategy("derived"), DerivedStrategy)


def test_derived_loader_inserts_metric_columns_and_upserts_by_composite_key() -> None:
    """Ensure derived loader SQL targets typed metric columns."""
    records = [_derived_record()]
    session = _CapturingSession()

    asyncio.run(DerivedStrategy().merge(session, "stg_test_derived", records))

    insert_statement = _find_statement_with_params(session, records)
    insert_sql = str(insert_statement)
    all_sql = "\n".join(str(statement) for statement, _ in session.calls)
    assert "net_net_working_capital" in insert_sql
    assert "return_on_equity" in insert_sql
    assert "ON CONFLICT (composite_key)" in all_sql
