"""Request model for insider transactions."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from common.requests.base import Request


class FetchInsiderTransactionsRequest(Request):
    """Command to fetch insider transactions."""

    request_type: Literal["fetch_insider_transactions"]
    max_filing_date: Optional[datetime] = None
