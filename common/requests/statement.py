"""`fetch_statement` request schema (skeleton).

Covers income statement, balance sheet, and cash flow. SimFin source
methods: `sf.load_income`, `sf.load_balance`, `sf.load_cashflow`.
"""
from __future__ import annotations

from typing import Literal

from common.requests.base import Request


class FetchStatementRequest(Request):
    """TODO: symbols, statement kind (income/balance/cashflow), period, variant."""

    request_type: Literal["fetch_statement"] = "fetch_statement"
