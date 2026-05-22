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
    template: str | None = None,
    variant: str | None = None,
    fiscal_year: int | None = None,
    part: int = 0,
) -> dict[str, Any]:
    """Write a list of Pydantic models to a Parquet file and return metadata.

    The path structure is:
    {shared_folder}/{dataset}/template={template}/variant={variant}/year={fiscal_year}/run_id={run_id}/part-{part:03d}.parquet
    """
    if not models:
        return {"count": 0, "path": "", "checksum": ""}

    base_dir = config.shared_folder_path / dataset

    # Build partition path
    if template:
        base_dir = base_dir / f"template={template}"
    if variant:
        base_dir = base_dir / f"variant={variant}"
    if fiscal_year is not None:
        base_dir = base_dir / f"year={fiscal_year}"

    target_dir = base_dir / f"run_id={run_id}"
    target_dir.mkdir(parents=True, exist_ok=True)

    filename = f"part-{part:03d}.parquet"
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
        "path": str(final_path),
        "checksum": checksum,
    }
