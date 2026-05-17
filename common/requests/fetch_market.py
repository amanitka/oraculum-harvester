"""`fetch_market` request schema."""

from __future__ import annotations

from typing import Literal

from common.requests.base import Request


class FetchMarketRequest(Request):
    """Request a fresh pull of market definitions."""

    request_type: Literal["fetch_market"] = "fetch_market"
