"""Orchestrates SEC 13F bulk ingestion.

One Fetch13FBulkRequest → one bulk ZIP download → two DataFileReadyEvent streams:
  - ``sec_13f_holding``  (chunked, ~250K rows per Parquet file)
  - ``sec_13f_filer``    (single Parquet, ~6K rows)
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import date

from common.domain.data_file_ready import DataFileReadyEvent, DataBatchCompleteEvent
from common.requests.sec_13f import Fetch13FBulkRequest
from harvester.providers.sec_13f_provider import Sec13FProvider
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)


class Sec13FService:
    """Fetch quarterly 13F bulk data and publish parquet events."""

    def __init__(self, provider: Sec13FProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: Fetch13FBulkRequest) -> None:
        """Download bulk ZIP, write chunked Parquet files, publish two event streams."""
        from harvester import publishers

        correlation_id  = str(request.correlation_id) if request.correlation_id else str(uuid.uuid4())
        year, quarter   = request.year, request.quarter
        period, filed   = self._derive_dates(year, quarter)

        logger.info("Starting 13F bulk ingestion for %dQ%d (correlation_id=%s)", year, quarter, correlation_id)

        zf = await asyncio.to_thread(self._provider.download_bulk_zip, year, quarter)

        try:
            await self._publish_holdings(zf, period, filed, correlation_id, publishers)
            await self._publish_filers(zf, period, correlation_id, publishers)
        finally:
            zf.close()

        logger.info("13F bulk ingestion complete for %dQ%d", year, quarter)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _publish_holdings(self, zf, period, filed, correlation_id, publishers) -> None:
        """Write holdings in chunks and publish one DataFileReadyEvent per chunk.

        After all parts are sent, publishes a DataBatchCompleteEvent so the Java
        consumer knows it is safe to run sp_compute_sec_holding_delta.
        """
        chunks      = list(self._provider.parse_holdings(zf, period, filed))
        total_parts = len(chunks)
        total_rows  = 0

        if total_parts == 0:
            logger.warning("No holding rows extracted from bulk ZIP — nothing to publish")
            return

        for part_num, chunk in enumerate(chunks):
            meta = await asyncio.to_thread(
                write_to_parquet,
                models=chunk,
                dataset="sec_13f_holding",
                correlation_id=correlation_id,
                market="us",
                part=part_num,
            )
            event = DataFileReadyEvent(
                dataset="sec_13f_holding",
                file_name=meta["path"],
                correlation_id=correlation_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
            )
            await publishers.data_file_ready.publish(
                event, key=f"sec_13f_holding:{correlation_id}"
            )
            total_rows += meta["count"]
            logger.info("Published sec_13f_holding part %d/%d (%d rows)", part_num + 1, total_parts, meta["count"])

        # Signal that all parts are on the wire — no file data, just a completion marker.
        await publishers.batch_complete.publish(
            DataBatchCompleteEvent(
                dataset="sec_13f_holding",
                correlation_id=correlation_id,
                total_parts=total_parts,
                period_of_report=period,
            ),
            key=f"sec_13f_holding:{correlation_id}",
        )
        logger.info("Published batch_complete for sec_13f_holding (%d total rows, %d parts)", total_rows, total_parts)


    async def _publish_filers(self, zf, period, correlation_id, publishers) -> None:
        """Write filers to a single Parquet file and publish one event."""
        filers = await asyncio.to_thread(self._provider.parse_filers, zf, period)

        if not filers:
            logger.warning("No filers extracted from bulk ZIP — nothing to publish")
            return

        meta = await asyncio.to_thread(
            write_to_parquet,
            models=filers,
            dataset="sec_13f_filer",
            correlation_id=correlation_id,
            market="us",
            part=0,
        )
        event = DataFileReadyEvent(
            dataset="sec_13f_filer",
            file_name=meta["path"],
            correlation_id=correlation_id,
            file_checksum=meta["checksum"],
            record_count=meta["count"],
        )
        await publishers.data_file_ready.publish(
            event, key=f"sec_13f_filer:{correlation_id}"
        )
        logger.info("Published sec_13f_filer (%d filers)", meta["count"])

    @staticmethod
    def _derive_dates(year: int, quarter: int) -> tuple[date, date]:
        """Derive period_of_report and an approximate filing_date from year+quarter."""
        quarter_end_month = quarter * 3
        quarter_end_day   = {3: 31, 6: 30, 9: 30, 12: 31}[quarter_end_month]
        period = date(year, quarter_end_month, quarter_end_day)
        # 13F filings are due 45 days after quarter end; bulk is published ~55 days after
        filed  = date(year if quarter < 4 else year + 1,
                      (quarter_end_month % 12) + 1 if quarter < 4 else 1,
                      15)
        return period, filed
