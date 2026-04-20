"""Derived financial ratios domain model (skeleton).

Populated when `FetchRatioCommand` is implemented. Source data comes
from SimFin `load_derived`: ROE, P/E, Debt-to-Equity, and similar.
"""
from __future__ import annotations

from pydantic import BaseModel


class Ratio(BaseModel):
    """TODO: define full schema (symbol, period, metric map)."""

    symbol: str
