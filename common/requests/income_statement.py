"""`fetch_income_statement` request schema."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from common.domain import IncomeStatementTemplate
from common.requests.base import Request

_ALL_TEMPLATES: tuple[IncomeStatementTemplate, ...] = ("general", "banks", "insurance")


class FetchIncomeStatementRequest(Request):
    """Pull SimFin income statements for one or more industry templates.

    `variant` selects the SimFin periodicity (annual, quarterly, ttm);
    `templates` selects which industry schemas to fetch. A single request
    fans out to every listed template and publishes all rows to the shared
    income-statement topic.
    """

    request_type: Literal["fetch_income_statement"] = "fetch_income_statement"
    market: str = "us"
    variant: Literal["annual", "quarterly", "ttm"] = "annual"
    templates: list[IncomeStatementTemplate] = Field(
        default_factory=lambda: list(_ALL_TEMPLATES)
    )
