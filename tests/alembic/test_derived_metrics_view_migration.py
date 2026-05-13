"""Tests for replacing persisted derived metrics with a database view."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType


def _load_migration() -> ModuleType:
    """Load the migration module by path."""
    migration_path = (
        Path(__file__).resolve().parents[2]
        / "alembic"
        / "versions"
        / "0002_create_derived_metrics_view.py"
    )
    spec = importlib.util.spec_from_file_location(
        "create_derived_metrics_view", migration_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load derived metrics view migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _load_migration()


def test_derived_metrics_view_uses_statement_tables_and_json_payloads() -> None:
    """Ensure derived metrics are calculated from persisted statement rows."""
    view_sql = _MIGRATION._DERIVED_METRICS_VIEW_SQL

    assert "CREATE VIEW v_derived_metrics" in view_sql
    assert "income.composite_key" in view_sql
    assert "FROM t_income_statement AS income" in view_sql
    assert "INNER JOIN t_balance_sheet AS balance" in view_sql
    assert "INNER JOIN t_cash_flow_statement AS cash_flow" in view_sql
    assert "income.payload ->> 'Net Income'" in view_sql
    assert "balance.payload ->> 'Total Equity'" in view_sql
    assert "cash_flow.payload ->> 'Net Cash from Operating Activities'" in view_sql


def test_derived_metrics_view_matches_current_formula_contract() -> None:
    """Ensure SQL formulas preserve the previous derived metric semantics."""
    view_sql = _MIGRATION._DERIVED_METRICS_VIEW_SQL

    assert "net_income\n        - COALESCE(interest_expense_net, 0)" in view_sql
    assert "COALESCE(net_cash_from_operating_activities, 0)" in view_sql
    assert "+ COALESCE(capital_expenditures, 0) AS free_cash_flow" in view_sql
    assert "total_current_assets - total_liabilities AS ncav" in view_sql
    assert "COALESCE(accounts_notes_receivable, 0) * 0.75" in view_sql
    assert "COALESCE(inventories, 0) * 0.5" in view_sql
    assert "COALESCE(shares_diluted, shares_basic) AS shares_stabilized" in view_sql
    assert "net_income / NULLIF(total_equity, 0) AS return_on_equity" in view_sql
    assert "net_income / NULLIF(revenue, 0) AS net_margin" in view_sql


def test_derived_metrics_view_uses_null_safe_restatement_join() -> None:
    """Ensure restated statement rows are joined with SQL null semantics."""
    view_sql = _MIGRATION._DERIVED_METRICS_VIEW_SQL

    assert "balance.restated_date IS NOT DISTINCT FROM income.restated_date" in view_sql
    assert "cash_flow.restated_date IS NOT DISTINCT FROM income.restated_date" in view_sql


def test_migration_is_squashed_after_initial_schema() -> None:
    """Ensure the derived table migration is no longer part of fresh installs."""
    assert _MIGRATION.down_revision == "0001_initial"
    assert "t_derived" not in _MIGRATION._DERIVED_METRICS_VIEW_SQL
