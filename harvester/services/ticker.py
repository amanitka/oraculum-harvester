"""Fetch + publish ticker metadata."""

from __future__ import annotations

import asyncio
import logging

from common.domain.data_file_ready import DataFileReadyEvent
from common.requests import FetchTickerRequest
from harvester.providers import SimFinProvider
from harvester.publishers import data_file_ready as data_file_ready_publisher
from harvester.publishers import ticker as ticker_publisher
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class TickerService:
    """Streams tickers from SimFin onto the ticker topic and shared Parquet."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchTickerRequest) -> None:
        """Materialise tickers in a worker thread, then publish one by one and to Parquet."""
        tickers = await asyncio.to_thread(
            lambda: list(self._provider.fetch_tickers(market=request.market))
        )

        # Original behaviour (direct topic publish)
        for ticker in tickers:
            await ticker_publisher.publish(ticker, key=ticker.symbol)

        # New behaviour (Parquet + notification)
        if tickers:
            run_id = str(request.correlation_id)
            meta = await asyncio.to_thread(
                write_to_parquet, models=tickers, dataset="ticker", run_id=run_id
            )

            event = DataFileReadyEvent(
                dataset="ticker",
                path=meta["path"],
                run_id=run_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )

            await data_file_ready_publisher.publish(event, key=f"ticker:{run_id}")

        logger.info(
            "Published %d tickers (Kafka + Parquet) [cid=%s market=%s]",
            len(tickers),
            request.correlation_id,
            request.market,
        )
