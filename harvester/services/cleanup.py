"""Background cleanup scheduler for harvester temporary files."""

from __future__ import annotations

import asyncio
import logging
import shutil
import time
from pathlib import Path

from common.config import config

logger = logging.getLogger(__name__)


class HarvesterTempCleanup:
    """Periodically scans and cleans up stale temporary files in harvester data directory."""

    def __init__(
        self,
        enabled: bool | None = None,
        retention_days: int | None = None,
        interval_days: int | None = None,
    ) -> None:
        self.enabled = config.harvester_temp_cleanup_enabled if enabled is None else enabled
        self.retention_days = (
            config.harvester_temp_cleanup_retention_days if retention_days is None else retention_days
        )
        self.interval_days = (
            config.harvester_temp_cleanup_interval_days if interval_days is None else interval_days
        )
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        """Start the background cleanup loop."""
        if not self.enabled:
            logger.info("Harvester temporary directory cleanup is disabled by configuration.")
            return

        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._loop(), name="harvester_temp_cleanup")
            logger.info(
                "Started Harvester temporary directory cleanup loop (retention: %dd, interval: %dd)",
                self.retention_days,
                self.interval_days,
            )

    def stop(self) -> None:
        """Stop the background cleanup loop."""
        if self._task and not self._task.done():
            self._task.cancel()
            logger.info("Stopped Harvester temporary directory cleanup loop.")

    async def _loop(self) -> None:
        sleep_seconds = self.interval_days * 86400
        while True:
            try:
                self.clean_stale_files()
            except Exception as exc:
                logger.error("Error during harvester temp directory cleanup: %s", exc)
            await asyncio.sleep(sleep_seconds)

    def clean_stale_files(self) -> None:
        """Scan harvester tmp directory and delete items older than retention threshold."""
        tmp_dir = config.harvester_data_directory / "tmp"
        if not tmp_dir.exists():
            return

        cutoff = time.time() - (self.retention_days * 86400)
        deleted_count = 0

        for item in tmp_dir.iterdir():
            try:
                mtime = item.stat().st_mtime
                if mtime < cutoff:
                    if item.is_dir():
                        shutil.rmtree(item, ignore_errors=True)
                    else:
                        item.unlink(missing_ok=True)
                    deleted_count += 1
                    logger.debug("Deleted stale harvester temporary item: %s", item)
            except Exception as e:
                logger.warning("Failed to clean up temporary path %s: %s", item, e)

        if deleted_count > 0:
            logger.info("Harvester temp cleanup finished: removed %d stale items", deleted_count)
