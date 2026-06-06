"""`fetch_share_price` request schema."""

from __future__ import annotations

from datetime import date
from typing import Literal, Optional

from common.requests.base import Request


class FetchSharePriceRequest(Request):
    """Pull SimFin daily share prices for a market.

    ``from_date=None`` triggers a full historical load; setting it enables
    incremental ingestion.  The harvester filters to rows with
    ``trade_date >= from_date``
    """

    request_type: Literal["fetch_share_price"] = "fetch_share_price"
    market: str = "us"
    variant: str = "daily"
    from_date: Optional[date] = None
