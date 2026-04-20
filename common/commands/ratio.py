"""`fetch_ratio` command schema (skeleton).

Covers pre-calculated financial metrics (ROE, P/E, Debt-to-Equity, ...).
SimFin source method: `sf.load_derived`.
"""
from __future__ import annotations

from typing import Literal

from common.commands.base import Command


class FetchRatioCommand(Command):
    """TODO: symbols, period."""

    command_type: Literal["fetch_ratio"] = "fetch_ratio"
