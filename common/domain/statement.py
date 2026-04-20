"""Financial statement domain model (skeleton).

Populated when `FetchStatementCommand` is implemented. Source data comes
from SimFin `load_income`, `load_balance`, `load_cashflow`.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

StatementKind = Literal["income", "balance", "cashflow"]


class Statement(BaseModel):
    """TODO: define full schema (symbol, period, kind, line items)."""

    symbol: str
    kind: StatementKind
