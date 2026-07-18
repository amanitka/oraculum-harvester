"""SharePriceService: fetch SimFin share prices and write to Parquet."""

from __future__ import annotations

import asyncio
import logging
from typing import List, Optional

from common.domain.data_file_ready import DataFileReadyEvent
from common.domain.share_price import SharePrice
from common.requests.share_price import FetchSharePriceRequest
from harvester.providers.simfin_provider import SimFinProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class SharePriceService:
    """Fetches share prices from SimFin and publishes them to Parquet."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchSharePriceRequest) -> None:
        """Fetch share prices, write to Parquet files in chunks and notify."""
        from harvester import publishers

        chunk_generator = self._provider.fetch_share_prices(
            market=request.market, variant=request.variant, from_date=request.from_date
        )

        def _get_next_chunk() -> Optional[List[SharePrice]]:
            try:
                return next(chunk_generator)
            except StopIteration:
                return None

        correlation_id = str(request.correlation_id)
        total_rows = 0
        part = 0

        while True:
            rows_chunk = await asyncio.to_thread(_get_next_chunk)
            if rows_chunk is None:
                break

            if not rows_chunk:
                continue

            meta = await asyncio.to_thread(
                write_to_parquet,
                models=rows_chunk,
                dataset="share_price",
                correlation_id=correlation_id,
                market=request.market,
                part=part,
            )

            event = DataFileReadyEvent(
                dataset="share_price",
                file_name=meta["path"],
                correlation_id=correlation_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )

            await publishers.data_file_ready.publish(event, key=f"share_price:{correlation_id}:{part}")

            total_rows += len(rows_chunk)
            part += 1
            del rows_chunk
            from common.memory import release_memory
            release_memory()

        logger.info(
            "Published %d share price rows in %d parts to Parquet [cid=%s market=%s from_date=%s]",
            total_rows,
            part,
            request.correlation_id,
            request.market,
            request.from_date,
        )

        # Explicitly clean up the generator and release memory back to the OS
        chunk_generator.close()
        del chunk_generator
        from common.memory import release_memory
        release_memory()
