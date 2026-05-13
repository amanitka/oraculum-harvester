"""Tests for scheduled data refresh request construction."""

from __future__ import annotations

from analyst.jobs.data_refresh import _build_fundamentals_requests


def test_fundamentals_refresh_excludes_derived_requests() -> None:
    """Ensure derived metrics are not scheduled as harvested datasets."""
    requests = _build_fundamentals_requests()
    request_types = [request.request_type for request in requests]

    assert "fetch_derived" not in request_types
    assert set(request_types) == {
        "fetch_income_statement",
        "fetch_balance_sheet",
        "fetch_cash_flow_statement",
    }
