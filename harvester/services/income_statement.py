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
    """Streams income statements from SimFin onto the topic."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchIncomeStatementRequest) -> None:
        """Fetch rows for all requested templates, publish to Kafka and Parquet."""
        from harvester import publishers

        publisher = getattr(publishers, "income_statement")

        for template in request.templates:
            rows = await asyncio.to_thread(
                lambda t=template: list(
                    getattr(self._provider, "fetch_income_statements")(
                        market=request.market,
                        variant=request.variant,
                        template=t,
                    )
                )
            )

            if not rows:
                continue

            for row in rows:
                await publisher.publish(row, key=row.composite_key)

            run_id = str(request.correlation_id)
            meta = await asyncio.to_thread(
                write_to_parquet,
                models=rows,
                dataset="income_statement",
                run_id=run_id,
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

            await publishers.data_file_ready.publish(
                event, key=f"income_statement:{run_id}"
            )

            logger.info(
                "Published %d rows for template '%s' (Kafka + Parquet) [cid=%s]",
                len(rows),
                template,
                request.correlation_id,
            )
