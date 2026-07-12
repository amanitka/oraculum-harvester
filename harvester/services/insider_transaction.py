"""Fetch + publish insider transactions."""

from __future__ import annotations

import asyncio
import logging
import uuid

from common.domain.data_file_ready import DataFileReadyEvent
from common.requests.insider_transaction import FetchInsiderTransactionsRequest
from harvester.providers.openinsider_provider import OpenInsiderProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class InsiderTransactionService:
    """Stream insider transactions from OpenInsider to Parquet and publish events."""

    def __init__(self, provider: OpenInsiderProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchInsiderTransactionsRequest) -> None:
        """Materialize transactions in a worker thread, then write to Parquet."""
        from harvester import publishers

        # Convert generator to a list in a background thread to block safely
        total_published = 0
        correlation_id = str(request.correlation_id) if request.correlation_id else str(uuid.uuid4())
        part_num = 0
        
        # The provider yields batches (typically month by month)
        for transactions_batch in self._provider.fetch_transactions(request.max_filing_date):
            if not transactions_batch:
                continue
            
            try:
                meta = await asyncio.to_thread(
                    write_to_parquet,
                    models=transactions_batch,
                    dataset="insider_transaction",
                    correlation_id=correlation_id,
                    market="us",  # OpenInsider is US only
                    part=part_num,
                )

                event = DataFileReadyEvent(
                    dataset="insider_transaction",
                    file_name=meta["path"],
                    correlation_id=correlation_id,
                    file_checksum=meta["checksum"],
                    record_count=meta["count"],
                )

                await publishers.data_file_ready.publish(event, key=f"insider_transaction:{correlation_id}")
                logger.info("Published DataFileReadyEvent for %d insider transactions (Correlation ID: %s, Part: %d)", meta["count"], correlation_id, part_num)
                total_published += meta["count"]
                part_num += 1
                
            except Exception as exc:
                logger.error("Failed to write parquet or publish batch: %s", exc)
                raise
                
        if total_published == 0:
            logger.info("No new transactions to process.")
        else:
            logger.info("Finished publishing all %d insider transactions.", total_published)
