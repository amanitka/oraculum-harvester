"""`fetch_ticker` command schema."""
from __future__ import annotations

from typing import Literal

from common.commands.base import Command


class FetchTickerCommand(Command):
    """Request a fresh pull of ticker master data from a provider."""

    command_type: Literal["fetch_ticker"] = "fetch_ticker"
    market: str = "us"
