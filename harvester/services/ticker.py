"""Fetch + publish ticker metadata."""

from __future__ import annotations

import asyncio
import logging

from common.domain.data_file_ready import DataFileReadyEvent
from common.requests import FetchTickerRequest
from harvester.providers import SimFinProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class TickerService:
    """Streams tickers from SimFin to Parquet and notifies via data_file_ready."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchTickerRequest) -> None:
        """Materialise tickers in a worker thread, then publish to Parquet."""
        from harvester import publishers

        tickers = await asyncio.to_thread(
            lambda: list(self._provider.fetch_tickers(market=request.market))
        )

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

            await publishers.data_file_ready.publish(event, key=f"ticker:{run_id}")

        logger.info(
            "Published %d tickers to Parquet [cid=%s market=%s]",
            len(tickers),
            request.correlation_id,
            request.market,
        )
