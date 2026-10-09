"""Orchestrates SEC 13F bulk ingestion.

One Fetch13FBulkRequest → one bulk ZIP download → two DataFileReadyEvent streams:
  - ``sec_13f_holding``  (chunked, ~250K rows per Parquet file)
  - ``sec_13f_filer``    (single Parquet, ~6K rows)
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import uuid
import zipfile
from datetime import date

from common.config import config
from common.domain.data_file_ready import DataFileReadyEvent, DataBatchCompleteEvent
from common.requests.sec_13f import Fetch13FBulkRequest
from harvester.providers.sec_13f_provider import Sec13FProvider
from harvester.services.parquet_writer import write_df_to_parquet, write_to_parquet

logger = logging.getLogger(__name__)


class Sec13FService:
    """Fetch quarterly 13F bulk data and publish parquet events."""

    def __init__(self, provider: Sec13FProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: Fetch13FBulkRequest) -> None:
        """Download bulk ZIP to temp file, stream chunked Parquet files, publish events, and clean up."""
        from harvester import publishers

        correlation_id  = str(request.correlation_id) if request.correlation_id else str(uuid.uuid4())
        year, quarter   = request.year, request.quarter
        period, filed   = self._derive_dates(year, quarter)

        logger.info("Starting 13F bulk ingestion for %dQ%d (period=%s, correlation_id=%s)", year, quarter, period, correlation_id)

        # Clean up any stale temporary directories older than 1 day from previous crashes
        self._cleanup_stale_temp_dirs()

        # Create temporary working directory for this batch
        tmp_dir = config.harvester_data_directory / "tmp" / f"sec_13f_{correlation_id}"
        tmp_zip = tmp_dir / f"{year}q{quarter}_bulk.zip"

        try:
            logger.info("Downloading bulk ZIP to %s...", tmp_zip)
            downloaded = await asyncio.to_thread(self._provider.download_to_file, year, quarter, tmp_zip)
            if downloaded is None or not downloaded.exists():
                logger.info("SEC 13F bulk dataset for %dQ%d is not yet available on any configured URL. Skipping processing.", year, quarter)
                return

            with zipfile.ZipFile(tmp_zip) as zf:
                logger.info("Processing institutional filers metadata...")
                await self._publish_filers(zf, period, correlation_id, publishers)

                logger.info("Streaming 13F holdings tables in chunks directly to Parquet...")
                await self._publish_holdings(zf, period, filed, correlation_id, publishers)

        finally:
            # Guaranteed cleanup of downloaded ZIP and temporary directory
            logger.info("Cleaning up temporary download directory %s...", tmp_dir)
            try:
                if tmp_dir.exists():
                    shutil.rmtree(tmp_dir, ignore_errors=True)
                logger.info("Cleanup completed for %s", tmp_dir)
            except Exception as e:
                logger.warning("Failed to remove temporary directory %s: %s", tmp_dir, e)

        logger.info("13F bulk ingestion completely finished for %dQ%d", year, quarter)

    # ------------------------------------------------------------------
    # Private
    # ------------------------------------------------------------------

    async def _publish_holdings(self, zf, period, filed, correlation_id, publishers) -> None:
        """Stream holdings in chunks and publish one DataFileReadyEvent per chunk.

        Processes and writes one DataFrame chunk at a time, avoiding multi-gigabyte RAM spikes.
        """
        part_num = 0
        total_rows = 0

        # Generator yields one transformed chunk DataFrame at a time
        for chunk_df in self._provider.stream_holdings_chunks(zf, period, filed):
            row_count = len(chunk_df)
            meta = await asyncio.to_thread(
                write_df_to_parquet,
                df=chunk_df,
                dataset="sec_13f_holding",
                correlation_id=correlation_id,
                market="us",
                part=part_num,
            )
            del chunk_df  # Free memory immediately

            event = DataFileReadyEvent(
                dataset="sec_13f_holding",
                file_name=meta["path"],
                correlation_id=correlation_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
                is_first_part=(part_num == 0),
            )
            await publishers.data_file_ready.publish(
                event, key=f"sec_13f_holding:{correlation_id}"
            )
            total_rows += row_count
            part_num += 1
            logger.info("Published sec_13f_holding part %d (%d rows) -> %s", part_num, row_count, meta["path"])

        total_parts = part_num
        if total_parts == 0:
            logger.warning("No holding rows extracted from bulk ZIP — nothing to publish")
            return

        # Signal that all parts are on the wire — no file data, just a completion marker.
        logger.info("Publishing DataBatchCompleteEvent for sec_13f_holding (%d total rows across %d parts)...", total_rows, total_parts)
        await publishers.batch_complete.publish(
            DataBatchCompleteEvent(
                dataset="sec_13f_holding",
                correlation_id=correlation_id,
                total_parts=total_parts,
                report_period=period,
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

        logger.info("Writing Parquet file for %d filers...", len(filers))
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
        logger.info("Published sec_13f_filer (%d filers) -> %s", meta["count"], meta["path"])

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

    @staticmethod
    def _cleanup_stale_temp_dirs() -> None:
        """Removes any orphaned temporary directories older than 24h from earlier crashed runs."""
        import time

        tmp_root = config.harvester_data_directory / "tmp"
        if not tmp_root.exists():
            return

        cutoff = time.time() - (24 * 3600)  # 24 hours ago
        for entry in tmp_root.iterdir():
            try:
                if entry.is_dir() and entry.name.startswith("sec_13f_"):
                    if entry.stat().st_mtime < cutoff:
                        logger.info("Cleaning up orphaned temp directory from previous run: %s", entry)
                        shutil.rmtree(entry, ignore_errors=True)
            except Exception as e:
                logger.warning("Error checking/cleaning temporary directory %s: %s", entry, e)
