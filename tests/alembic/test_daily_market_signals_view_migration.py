"""Tests for adding the daily market signals database view."""

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
            / "0006_daily_market_signals_view.py"
    )
    spec = importlib.util.spec_from_file_location(
        "daily_market_signals_view", migration_path
    )
    if spec is None or spec.loader is None:
        raise RuntimeError("Cannot load daily market signals view migration.")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_MIGRATION = _load_migration()


def test_daily_market_signals_view_uses_ttm_fundamentals_and_share_prices() -> None:
    """Ensure signals are joined from price history and TTM-derived fundamentals."""
    view_sql = _MIGRATION._DAILY_MARKET_SIGNALS_VIEW_SQL

    assert "CREATE OR REPLACE VIEW v_daily_market_signals" in view_sql
    assert "FROM v_derived_metrics" in view_sql
    assert "WHERE variant = 'ttm'" in view_sql
    assert "FROM t_share_price p" in view_sql


def test_daily_market_signals_view_keeps_point_in_time_window_contract() -> None:
    """Ensure fundamentals are joined only across their explicit validity windows."""
    view_sql = _MIGRATION._DAILY_MARKET_SIGNALS_VIEW_SQL

    assert "LEAD(publish_date, 1, '9999-12-31'::date)" in view_sql
    assert "AND p.trade_date >= f.valid_from" in view_sql
    assert "AND p.trade_date < f.valid_to" in view_sql


def test_daily_market_signals_view_includes_technical_and_value_signal_formulas() -> None:
    """Ensure core moving-average and Graham-style formulas are present."""
    view_sql = _MIGRATION._DAILY_MARKET_SIGNALS_VIEW_SQL

    assert "ROWS BETWEEN 49 PRECEDING AND CURRENT ROW" in view_sql
    assert "ROWS BETWEEN 199 PRECEDING AND CURRENT ROW" in view_sql
    assert "AS pct_from_50d_ma" in view_sql
    assert "AS pct_from_200d_ma" in view_sql
    assert "AS volume_velocity" in view_sql
    assert "AS is_graham_net_net" in view_sql


def test_daily_market_signals_migration_chain_and_drop_contract() -> None:
    """Ensure migration ordering and downgrade drop target stay stable."""
    assert _MIGRATION.down_revision == "0005"
    assert "DROP VIEW IF EXISTS v_daily_market_signals" in _MIGRATION.downgrade.__code__.co_consts
