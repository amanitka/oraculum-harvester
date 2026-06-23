"""Fetch + publish insider transactions."""

from __future__ import annotations

import asyncio
import logging

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
        transactions = await asyncio.to_thread(
            lambda: list(self._provider.fetch_transactions(max_filing_date=request.max_filing_date))
        )

        if transactions:
            run_id = str(request.correlation_id)
            meta = await asyncio.to_thread(
                write_to_parquet,
                models=transactions,
                dataset="insider_transaction_ticker",
                run_id=run_id,
                market="us",  # OpenInsider is US only
            )

            event = DataFileReadyEvent(
                dataset="insider_transaction_ticker",
                path=meta["path"],
                run_id=run_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )

            await publishers.data_file_ready.publish(event, key=f"insider_transaction:{run_id}")

        logger.info(
            "Published %d insider transactions to Parquet [cid=%s max_filing_date=%s]",
            len(transactions),
            request.correlation_id,
            request.max_filing_date,
        )
