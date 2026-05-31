"""`fetch_company` request schema."""

from __future__ import annotations

from typing import Literal

from common.requests.base import Request


class FetchCompanyRequest(Request):
    """Request a fresh pull of company master data."""

    request_type: Literal["fetch_company"] = "fetch_company"
    market: str = "us"
