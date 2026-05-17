"""`fetch_industry` request schema."""

from __future__ import annotations

from typing import Literal

from common.requests.base import Request


class FetchIndustryRequest(Request):
    """Request a fresh pull of industry and sector definitions."""

    request_type: Literal["fetch_industry"] = "fetch_industry"
