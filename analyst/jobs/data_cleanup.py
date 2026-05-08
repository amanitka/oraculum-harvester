"""Scheduled cleanup job for data files."""

from __future__ import annotations

import logging
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)

_SECONDS_PER_DAY = 24 * 60 * 60
_DEFAULT_MISFIRE_GRACE_SECONDS: int = 300
_DATA_CLEANUP_JOB_ID: str = "cleanup_data_files"
_JOB_DEFAULTS: dict[str, bool | int] = {
    "coalesce": True,
    "max_instances": 1,
    "misfire_grace_time": _DEFAULT_MISFIRE_GRACE_SECONDS,
}


def cleanup_data_files(
    root_path: Path,
    *,
    retention_days: int,
    now: datetime | None = None,
) -> int:
    """Delete stale data files and return the deleted file count."""
    _validate_retention_days(retention_days)
    if not root_path.exists():
        logger.warning("Data cleanup skipped missing folder: %s", root_path)
        return 0
    if not root_path.is_dir():
        raise NotADirectoryError(str(root_path))

    cutoff_timestamp = _cutoff_timestamp(retention_days, now)
    deleted_count = 0
    for file_path in _iter_expired_files(root_path, cutoff_timestamp):
        if _delete_file(file_path):
            deleted_count += 1
    pruned_count = _prune_empty_directories(root_path)

    logger.info(
        "Deleted %d data files and pruned %d directories older than %d days under %s",
        deleted_count,
        pruned_count,
        retention_days,
        root_path,
    )
    return deleted_count


def create_data_cleanup_scheduler(
    root_path: Path,
    *,
    cron_expression: str,
    retention_days: int,
) -> AsyncIOScheduler:
    """Create an APScheduler instance for data cleanup."""
    _validate_retention_days(retention_days)
    scheduler = AsyncIOScheduler(job_defaults=_JOB_DEFAULTS)
    scheduler.add_job(
        func=cleanup_data_files,
        trigger=CronTrigger.from_crontab(cron_expression),
        kwargs={"root_path": root_path, "retention_days": retention_days},
        id=_DATA_CLEANUP_JOB_ID,
        replace_existing=True,
    )
    logger.info(
        "Data cleanup job configured [cron=%s retention_days=%d]",
        cron_expression,
        retention_days,
    )
    return scheduler


def _validate_retention_days(retention_days: int) -> None:
    if retention_days < 1:
        raise ValueError("retention_days must be a positive integer")


def _cutoff_timestamp(retention_days: int, now: datetime | None) -> float:
    reference_time = now or datetime.now(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    return reference_time.timestamp() - retention_days * _SECONDS_PER_DAY


def _iter_expired_files(root_path: Path, cutoff_timestamp: float) -> Iterator[Path]:
    try:
        for file_path in root_path.rglob("*"):
            if _is_expired_file(file_path, cutoff_timestamp):
                yield file_path
    except OSError:
        logger.warning("Unable to scan data files under %s", root_path, exc_info=True)


def _is_expired_file(file_path: Path, cutoff_timestamp: float) -> bool:
    try:
        return file_path.is_file() and file_path.stat().st_mtime < cutoff_timestamp
    except FileNotFoundError:
        logger.debug("Data file disappeared before inspection: %s", file_path)
        return False
    except OSError:
        logger.warning("Unable to inspect data path: %s", file_path, exc_info=True)
        return False


def _delete_file(file_path: Path) -> bool:
    try:
        file_path.unlink()
    except FileNotFoundError:
        logger.debug("Data file disappeared before cleanup: %s", file_path)
        return False
    except OSError:
        logger.warning("Unable to delete data file: %s", file_path, exc_info=True)
        return False
    return True


def _prune_empty_directories(root_path: Path) -> int:
    directory_paths = _collect_directories_deepest_first(root_path)
    pruned_count = 0
    for directory_path in directory_paths:
        if _delete_empty_directory(directory_path):
            pruned_count += 1
    return pruned_count


def _collect_directories_deepest_first(root_path: Path) -> list[Path]:
    try:
        return sorted(
            (path for path in root_path.rglob("*") if path.is_dir()),
            key=lambda path: len(path.parts),
            reverse=True,
        )
    except OSError:
        logger.warning(
            "Unable to scan data directories under %s",
            root_path,
            exc_info=True,
        )
        return []


def _delete_empty_directory(directory_path: Path) -> bool:
    try:
        directory_path.rmdir()
    except OSError:
        return False
    return True
