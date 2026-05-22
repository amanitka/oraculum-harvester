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
    """Streams balance sheets from SimFin to Parquet and notifies via data_file_ready."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchBalanceSheetRequest) -> None:
        """Fetch rows for all requested templates, publish to Parquet."""
        from harvester import publishers

        for template in request.templates:
            rows = await asyncio.to_thread(
                lambda t=template: list(
                    self._provider.fetch_balance_sheet(
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

            await publishers.data_file_ready.publish(event, key=f"balance_sheet:{run_id}")

            logger.info(
                "Published %d rows for template '%s' to Parquet [cid=%s]",
                len(rows),
                template,
                request.correlation_id,
            )
