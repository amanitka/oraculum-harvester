"""Fetch + publish balance sheets."""

from __future__ import annotations

import asyncio
import logging

from common.domain.data_file_ready import DataFileReadyEvent
from common.requests.balance_sheet import FetchBalanceSheetRequest
from harvester.providers import SimFinProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class BalanceSheetService:
    """Streams balance sheets from SimFin onto the topic."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchBalanceSheetRequest) -> None:
        """Fetch rows for all requested templates, publish to Kafka and Parquet."""
        from harvester import publishers

        publisher = getattr(publishers, "balance_sheet")

        for template in request.templates:
            rows = await asyncio.to_thread(
                lambda t=template: list(
                    getattr(self._provider, "fetch_balance_sheets")(
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
                dataset="balance_sheet",
                run_id=run_id,
                template=template,
                variant=request.variant,
            )

            event = DataFileReadyEvent(
                dataset="balance_sheet",
                path=meta["path"],
                template=template,
                variant=request.variant,
                run_id=run_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )

            await publishers.data_file_ready.publish(
                event, key=f"balance_sheet:{run_id}"
            )

            logger.info(
                "Published %d rows for template '%s' (Kafka + Parquet) [cid=%s]",
                len(rows),
                template,
                request.correlation_id,
            )
