"""Request model for fetching news data."""

from __future__ import annotations

from typing import Literal, Optional

from common.requests.base import Request


class FetchNewsRequest(Request):
    """Command to fetch news and sentiment data."""

    request_type: Literal["fetch_news"] = "fetch_news"
    time_from: Optional[str] = None
    time_to: Optional[str] = None
