"""SharePriceService: fetch SimFin share prices and write to Parquet."""

from __future__ import annotations

import asyncio
import logging

from common.domain.data_file_ready import DataFileReadyEvent
from common.requests.share_price import FetchSharePriceRequest
from harvester.providers.simfin_provider import SimFinProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class SharePriceService:
    """Fetches share prices from SimFin and publishes them to Parquet."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchSharePriceRequest) -> None:
        """Fetch share prices, write to a single Parquet file and notify."""
        from harvester import publishers

        rows = await asyncio.to_thread(
            lambda: list(
                self._provider.fetch_share_prices(
                    market=request.market,
                    variant=request.variant,
                    from_date=request.from_date,
                    safety_window_days=request.safety_window_days,
                )
            )
        )

        if rows:
            run_id = str(request.correlation_id)
            meta = await asyncio.to_thread(
                write_to_parquet, models=rows, dataset="share_price", run_id=run_id
            )

            event = DataFileReadyEvent(
                dataset="share_price",
                path=meta["path"],
                run_id=run_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )

            await publishers.data_file_ready.publish(event, key=f"share_price:{run_id}")

        logger.info(
            "Published %d share price rows to Parquet [cid=%s market=%s from_date=%s]",
            len(rows),
            request.correlation_id,
            request.market,
            request.from_date,
        )
