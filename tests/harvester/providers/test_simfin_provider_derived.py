"""Tests for SimFin derived metric calculations."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from simfin.names import (
    ACC_NOTES_RECV,
    CAPEX,
    CASH_EQUIV_ST_INVEST,
    DEPR_AMOR,
    INCOME_TAX,
    INTEREST_EXP_NET,
    INVENTORIES,
    NET_CASH_OPS,
    NET_INCOME,
    REVENUE,
    SHARES_BASIC,
    SHARES_DILUTED,
    TOTAL_CUR_ASSETS,
    TOTAL_EQUITY,
    TOTAL_LIABILITIES,
)

from harvester.providers.simfin_provider import SimFinProvider


def test_derived_calculation_merges_sources_and_calculates_metrics() -> None:
    """Ensure merged statement rows produce expected derived metrics."""
    extracted_at = datetime(2026, 5, 12, tzinfo=timezone.utc)
    merged = SimFinProvider._merge_derived_sources(
        _income_frame(revenue=100.0),
        _balance_frame(total_equity=50.0),
        _cash_flow_frame(),
    )

    frame = SimFinProvider._calculate_derived_metrics(
        merged,
        "general",
        "ttm",
        extracted_at,
    )
    row = frame.iloc[0]
    derived = SimFinProvider._data_row_to_derived(row, "general")

    assert derived is not None
    assert derived.composite_key == "ABC-2024-FY-general-ttm"
    assert derived.ebitda == 123.0
    assert derived.free_cash_flow == 35.0
    assert derived.ncav == 80.0
    assert derived.net_net_working_capital == 25.0
    assert derived.shares_stabilized == 9.0
    assert derived.return_on_equity == 2.0
    assert derived.net_margin == 1.0


def test_derived_calculation_returns_none_for_zero_denominator_ratio() -> None:
    """Ensure invalid ratio denominators are represented as missing values."""
    extracted_at = datetime(2026, 5, 12, tzinfo=timezone.utc)
    merged = SimFinProvider._merge_derived_sources(
        _income_frame(revenue=0.0),
        _balance_frame(total_equity=0.0),
        _cash_flow_frame(),
    )

    frame = SimFinProvider._calculate_derived_metrics(
        merged,
        "general",
        "annual",
        extracted_at,
    )
    derived = SimFinProvider._data_row_to_derived(frame.iloc[0], "general")

    assert derived is not None
    assert derived.return_on_equity is None
    assert derived.net_margin is None


def _base_identity() -> dict[str, object]:
    return {
        "Ticker": "ABC",
        "SimFinId": 1,
        "Currency": "USD",
        "Fiscal Year": 2024,
        "Fiscal Period": "FY",
        "Report Date": "2024-12-31",
        "Publish Date": "2025-02-01",
        "Restated Date": None,
    }


def _income_frame(revenue: float) -> pd.DataFrame:
    payload = _base_identity()
    payload.update(
        {
            NET_INCOME: 100.0,
            INTEREST_EXP_NET: -5.0,
            INCOME_TAX: -8.0,
            REVENUE: revenue,
            SHARES_DILUTED: None,
            SHARES_BASIC: 9.0,
        }
    )
    return pd.DataFrame([payload])


def _balance_frame(total_equity: float) -> pd.DataFrame:
    payload = _base_identity()
    payload.update(
        {
            TOTAL_CUR_ASSETS: 150.0,
            TOTAL_LIABILITIES: 70.0,
            CASH_EQUIV_ST_INVEST: 20.0,
            ACC_NOTES_RECV: 60.0,
            INVENTORIES: 60.0,
            TOTAL_EQUITY: total_equity,
        }
    )
    return pd.DataFrame([payload])


def _cash_flow_frame() -> pd.DataFrame:
    payload = _base_identity()
    payload.update(
        {
            DEPR_AMOR: 10.0,
            NET_CASH_OPS: 50.0,
            CAPEX: -15.0,
        }
    )
    return pd.DataFrame([payload])
