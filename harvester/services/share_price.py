"""SharePriceService: fetch SimFin share prices and publish batches to Kafka."""

from __future__ import annotations

import asyncio
import logging
from typing import Iterator

from common.domain.data_file_ready import DataFileReadyEvent
from common.domain.share_price import SharePrice, SharePriceBatch
from common.requests.share_price import FetchSharePriceRequest
from harvester.providers.simfin_provider import SimFinProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)

_BATCH_SIZE = 500


def _chunk(rows: list[SharePrice], size: int) -> Iterator[list[SharePrice]]:
    """Yield successive fixed-size slices of ``rows``."""
    for i in range(0, len(rows), size):
        yield rows[i : i + size]


class SharePriceService:
    """Fetches share prices from SimFin and publishes them in batches to Kafka."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchSharePriceRequest) -> None:
        """Fetch share prices, chunk into batches, and publish each batch."""
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

        total_rows = 0
        batch_num = 0

        # Original behaviour: chunked Kafka messages
        for chunk in _chunk(rows, _BATCH_SIZE):
            msg = SharePriceBatch(
                market=request.market,
                from_date=request.from_date,
                rows=chunk,
            )
            await publishers.share_price_batch.publish(
                msg, key=f"{request.market}:{batch_num}"
            )
            total_rows += len(chunk)
            batch_num += 1

        # New behaviour: write all to a single Parquet file and notify
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
            "Published %d share price rows in %d batches (Kafka + Parquet) [cid=%s market=%s from_date=%s]",
            total_rows,
            batch_num,
            request.correlation_id,
            request.market,
            request.from_date,
        )
