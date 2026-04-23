"""`fetch_cash_flow_statement` request schema."""
from __future__ import annotations

from typing import Literal

from pydantic import Field

from common.domain import CashFlowStatementTemplate
from common.requests.base import Request

_ALL_TEMPLATES: tuple[CashFlowStatementTemplate, ...] = ("general", "banks", "insurance")


class FetchCashFlowStatementRequest(Request):
    """Pull SimFin cash flow statements for one or more industry templates.

    `variant` selects the SimFin periodicity (annual, quarterly, ttm);
    `templates` selects which industry schemas to fetch. A single request
    fans out to every listed template and publishes all rows to the shared
    cash-flow-statement topic.
    """

    request_type: Literal["fetch_cash_flow_statement"] = "fetch_cash_flow_statement"
    market: str = "us"
    variant: Literal["annual", "quarterly", "ttm"] = "annual"
    templates: list[CashFlowStatementTemplate] = Field(
        default_factory=lambda: list(_ALL_TEMPLATES)
    )
