"""`fetch_ticker` request schema."""

from __future__ import annotations

from typing import Literal

from common.requests.base import Request


class FetchTickerRequest(Request):
    """Request a fresh pull of ticker master data."""

    request_type: Literal["fetch_ticker"] = "fetch_ticker"
    market: str = "us"
