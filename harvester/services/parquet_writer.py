"""Utility for writing Pydantic models to Parquet files."""

from __future__ import annotations

import hashlib
import logging
import os
from pathlib import Path
from typing import Any, List

import pandas as pd
from pydantic import BaseModel

from common.config import config

logger = logging.getLogger(__name__)


def compute_checksum(file_path: Path) -> str:
    """Compute SHA-256 checksum of a file."""
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def write_to_parquet(
    models: List[BaseModel],
    dataset: str,
    run_id: str,
    market: str,
    template: str | None = None,
    variant: str | None = None,
    fiscal_year: int | None = None,
    part: int = 0,
) -> dict[str, Any]:
    """Write a list of Pydantic models to a Parquet file and return metadata.

    All files are stored flatly in the harvester export folder.
    """
    if not models:
        return {"count": 0, "path": "", "checksum": ""}

    target_dir = config.harvester_export_folder_path
    target_dir.mkdir(parents=True, exist_ok=True)

    # Build unique filename
    if dataset in ("balance_sheet", "income_statement", "cash_flow_statement"):
        filename = f"{run_id}_{market}_{dataset}_{template or ''}_{variant or ''}_part-{part:03d}.parquet"
    else:
        filename = f"{run_id}_{market}_{dataset}_part-{part:03d}.parquet"

    tmp_path = target_dir / f"{filename}.tmp"
    final_path = target_dir / filename

    # Convert to DataFrame
    # model_dump(by_alias=False) keeps Python field names, so columns match target table schema roughly.
    df = pd.DataFrame([m.model_dump(mode="json", by_alias=False) for m in models])

    # Write to tmp
    df.to_parquet(tmp_path, index=False, engine="pyarrow")

    # Compute checksum
    checksum = compute_checksum(tmp_path)

    # Atomic rename
    os.rename(tmp_path, final_path)

    logger.debug("Wrote %d rows to %s", len(df), final_path)

    return {
        "count": len(df),
        "path": filename,
        "checksum": checksum,
    }
