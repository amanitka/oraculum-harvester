"""Fetch + publish ticker metadata."""

from __future__ import annotations

import asyncio
import logging

from common.requests import FetchTickerRequest
from harvester.providers import SimFinProvider
from harvester.publishers import ticker as ticker_publisher

logger = logging.getLogger(__name__)


class TickerService:
    """Streams tickers from SimFin onto the ticker topic."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchTickerRequest) -> None:
        """Materialise tickers in a worker thread, then publish one by one."""
        tickers = await asyncio.to_thread(
            lambda: list(self._provider.fetch_tickers(market=request.market))
        )
        for ticker in tickers:
            await ticker_publisher.publish(ticker, key=ticker.symbol)
        logger.info(
            "Published %d tickers [cid=%s market=%s]",
            len(tickers),
            request.correlation_id,
            request.market,
        )
