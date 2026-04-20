"""`fetch_statement` command schema (skeleton).

Will cover income statement, balance sheet, and cash flow. SimFin source
methods: `sf.load_income`, `sf.load_balance`, `sf.load_cashflow`.
"""
from __future__ import annotations

from typing import Literal

from common.commands.base import Command


class FetchStatementCommand(Command):
    """TODO: symbols, statement kind (income/balance/cashflow), period, variant."""

    command_type: Literal["fetch_statement"] = "fetch_statement"
