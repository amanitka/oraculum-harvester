"""`fetch_derived` request schema."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from common.domain import DerivedTemplate
from common.requests.base import Request

_ALL_TEMPLATES: tuple[DerivedTemplate, ...] = ("general",)


class FetchDerivedRequest(Request):
    """Pull SimFin source statements and calculate derived metrics."""

    request_type: Literal["fetch_derived"] = "fetch_derived"
    market: str = "us"
    variant: Literal["annual", "quarterly", "ttm"] = "annual"
    templates: list[DerivedTemplate] = Field(default_factory=lambda: list(_ALL_TEMPLATES))
