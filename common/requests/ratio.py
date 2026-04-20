"""`fetch_ratio` request schema (skeleton).

Covers pre-calculated financial metrics (ROE, P/E, Debt-to-Equity, ...).
SimFin source method: `sf.load_derived`.
"""
from __future__ import annotations

from typing import Literal

from common.requests.base import Request


class FetchRatioRequest(Request):
    """TODO: symbols, period."""

    request_type: Literal["fetch_ratio"] = "fetch_ratio"
