"""Fetch + publish company metadata."""

from __future__ import annotations

import asyncio
import logging

from common.domain.data_file_ready import DataFileReadyEvent
from common.requests import FetchCompanyRequest
from harvester.providers import SimFinProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class CompanyService:
    """Stream companies from SimFin to Parquet and publish data-file-ready events."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchCompanyRequest) -> None:
        """Materialize companies in a worker thread, then write to Parquet."""
        from harvester import publishers

        companies = await asyncio.to_thread(lambda: list(self._provider.fetch_companies(market=request.market)))

        if companies:
            run_id = str(request.correlation_id)
            meta = await asyncio.to_thread(
                write_to_parquet,
                models=companies,
                dataset="company",
                run_id=run_id,
            )

            event = DataFileReadyEvent(
                dataset="company",
                path=meta["path"],
                run_id=run_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )

            await publishers.data_file_ready.publish(event, key=f"company:{run_id}")

        logger.info(
            "Published %d companies to Parquet [cid=%s market=%s]",
            len(companies),
            request.correlation_id,
            request.market,
        )
