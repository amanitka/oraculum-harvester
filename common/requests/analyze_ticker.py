"""Request model for triggering a ticker analysis."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import Field

from common.domain.income_statement import StatementVariant
from common.requests.base import Request


class AnalyzeTickerRequest(Request):
    """
    A request to perform a deep analysis of a specific stock ticker.

    This triggers a multi-agent workflow that assesses fundamentals, cash flow,
    valuation, and risks, culminating in a synthesized report.
    """

    request_type: Literal["analyze_ticker"] = "analyze_ticker"
    ticker: str = Field(..., description="The ticker symbol to analyze (e.g., 'AAPL').")
    market: str = Field("us", description="The market code (e.g., 'us').")
    as_of: date | None = Field(None, description="The date for which to run the analysis, defaults to latest.")
    default_variant: StatementVariant = Field(
        "annual",
        description="The default statement variant (annual, quarterly, ttm) for agents to use.",
    )
