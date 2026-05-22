"""Regression tests for statement loader JSONB payload binding."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy.dialects import postgresql
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.sql.elements import TextClause

from analyst.infrastructure.loaders.balance_sheet import BalanceSheetStrategy
from analyst.infrastructure.loaders.cash_flow_statement import CashFlowStatementStrategy
from analyst.infrastructure.loaders.income_statement import IncomeStatementStrategy


class _CapturingSession:
    def __init__(self) -> None:
        self.calls: list[tuple[Any, list[dict[str, Any]] | None]] = []

    async def exec(self, statement: Any, params: list[dict[str, Any]] | None = None) -> None:
        self.calls.append((statement, params))


def _statement_record() -> dict[str, Any]:
    return {
        "composite_key": "ABC-2024-Q1-standard-ttm",
        "template": "standard",
        "variant": "ttm",
        "ticker": "ABC",
        "simfin_id": 1,
        "currency": "USD",
        "fiscal_year": 2024,
        "fiscal_period": "Q1",
        "report_date": "2024-03-31",
        "publish_date": "2024-04-30",
        "restated_date": None,
        "extracted_at": "2026-05-08T10:42:57.023083Z",
        "payload": {"Net Income": 1},
    }


def _find_insert_statement(session: _CapturingSession, records: list[dict[str, Any]]) -> Any:
    for statement, params in session.calls:
        if params is records:
            return statement
    raise AssertionError("statement loader did not execute a parameterized staging insert")


async def _insert_statement_for(strategy: Any) -> TextClause:
    records = [_statement_record()]
    session = _CapturingSession()
    await strategy.merge(session, "stg_test_statement", records)
    insert_statement = _find_insert_statement(session, records)
    assert isinstance(insert_statement, TextClause)
    return insert_statement


def test_statement_loaders_bind_payload_as_jsonb() -> None:
    """Ensure statement loader payloads are bound as PostgreSQL JSONB."""
    strategies = [
        IncomeStatementStrategy(),
        BalanceSheetStrategy(),
        CashFlowStatementStrategy(),
    ]

    for strategy in strategies:
        statement = asyncio.run(_insert_statement_for(strategy))
        compiled = statement.compile(dialect=postgresql.dialect())
        assert type(compiled.binds["payload"].type) is JSONB
