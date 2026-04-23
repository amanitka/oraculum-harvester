"""`fetch_balance_sheet` request schema."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from common.domain import BalanceSheetTemplate
from common.requests.base import Request

_ALL_TEMPLATES: tuple[BalanceSheetTemplate, ...] = ("general", "banks", "insurance")


class FetchBalanceSheetRequest(Request):
    """Pull SimFin balance sheets for one or more industry templates.

    `variant` selects the SimFin periodicity (annual, quarterly, ttm);
    `templates` selects which industry schemas to fetch. A single request
    fans out to every listed template and publishes all rows to the shared
    balance-sheet topic.
    """

    request_type: Literal["fetch_balance_sheet"] = "fetch_balance_sheet"
    market: str = "us"
    variant: Literal["annual", "quarterly", "ttm"] = "annual"
    templates: list[BalanceSheetTemplate] = Field(
        default_factory=lambda: list(_ALL_TEMPLATES)
    )
