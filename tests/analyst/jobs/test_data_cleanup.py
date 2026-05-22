"""Tests for scheduled data cleanup."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from analyst.jobs.data_cleanup import cleanup_data_files

_SECONDS_PER_DAY = 24 * 60 * 60


def test_cleanup_deletes_only_expired_files(tmp_path: Path) -> None:
    """Ensure cleanup removes old files while preserving fresh files."""
    now = datetime(2026, 5, 8, tzinfo=timezone.utc)
    root_path = tmp_path / "data"
    old_parquet = _touch_file(root_path / "shared" / "ticker" / "run_id=old" / "part-000.parquet", now, 4)
    old_tmp = _touch_file(
        root_path / "shared" / "ticker" / "run_id=old_tmp" / "part-000.parquet.tmp",
        now,
        5,
    )
    old_text = _touch_file(root_path / "simfin_cache" / "stale.txt", now, 10)
    fresh_parquet = _touch_file(
        root_path / "shared" / "ticker" / "run_id=fresh" / "part-000.parquet",
        now,
        1,
    )

    deleted_count = cleanup_data_files(root_path, retention_days=3, now=now)

    assert deleted_count == 3
    assert not old_parquet.exists()
    assert not old_tmp.exists()
    assert not old_text.exists()
    assert not old_parquet.parent.exists()
    assert not old_tmp.parent.exists()
    assert not old_text.parent.exists()
    assert fresh_parquet.exists()


def test_cleanup_requires_positive_retention_days(tmp_path: Path) -> None:
    """Reject retention settings that would purge all files accidentally."""
    with pytest.raises(ValueError, match="retention_days"):
        cleanup_data_files(tmp_path, retention_days=0)


def _touch_file(path: Path, now: datetime, age_days: int) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("test", encoding="utf-8")
    timestamp = now.timestamp() - age_days * _SECONDS_PER_DAY
    os.utime(path, (timestamp, timestamp))
    return path
