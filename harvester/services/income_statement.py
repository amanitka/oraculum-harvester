"""Fetch + publish income statements."""

from __future__ import annotations

import asyncio
import logging

from common.domain.data_file_ready import DataFileReadyEvent
from common.requests.income_statement import FetchIncomeStatementRequest
from harvester.providers import SimFinProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class IncomeStatementService:
    """Streams income statements from SimFin to Parquet and notifies via data_file_ready."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchIncomeStatementRequest) -> None:
        """Fetch rows for all requested templates, publish to Parquet."""
        from harvester import publishers

        for template in request.templates:
            rows = await asyncio.to_thread(
                lambda t=template: list(
                    getattr(self._provider, "fetch_income")(
                        market=request.market,
                        variant=request.variant,
                        template=t,
                    )
                )
            )

            if not rows:
                continue

            run_id = str(request.correlation_id)
            meta = await asyncio.to_thread(
                write_to_parquet,
                models=rows,
                dataset="income_statement",
                run_id=run_id,
                market=request.market,
                template=template,
                variant=request.variant,
            )

            event = DataFileReadyEvent(
                dataset="income_statement",
                path=meta["path"],
                template=template,
                variant=request.variant,
                run_id=run_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )

            await publishers.data_file_ready.publish(event, key=f"income_statement:{run_id}")

            logger.info(
                "Published %d rows for template '%s' to Parquet [cid=%s]",
                len(rows),
                template,
                request.correlation_id,
            )
