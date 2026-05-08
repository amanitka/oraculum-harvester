"""Bulk loads Parquet files into PostgreSQL staging tables."""

from __future__ import annotations

import logging
import time

import pandas as pd
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.loaders.factory import get_strategy
from analyst.infrastructure.models.run_log import IngestionRunLogDB
from common.domain.data_file_ready import DataFileReadyEvent

logger = logging.getLogger(__name__)


# noinspection PyTypeChecker,PyArgumentList
class ParquetLoader:
    """Orchestrates Parquet to PostgreSQL bulk loads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, event: DataFileReadyEvent) -> None:
        """Load a Parquet file idempotently based on the event payload."""
        if await self._is_already_processed(event):
            logger.info(
                "Skipping already processed event: %s (run_id=%s)",
                event.dataset,
                event.run_id,
            )
            return

        start_time = time.monotonic()
        run_log = IngestionRunLogDB(
            dataset=event.dataset,
            run_id=event.run_id,
            file_checksum=event.file_checksum,
            status="RUNNING",
        )
        self._session.add(run_log)
        await self._session.commit()
        await self._session.refresh(run_log)

        try:
            loaded, merged = await self._process_dataset(event)
            run_log.status = "SUCCESS"
            run_log.loaded_rows = loaded
            run_log.merged_rows = merged
        except Exception as e:
            logger.exception("Failed to load dataset: %s", event.dataset)
            await self._session.rollback()
            run_log.status = "FAILED"
            run_log.error_text = str(e)
            raise
        finally:
            run_log.duration_ms = int((time.monotonic() - start_time) * 1000)
            self._session.add(run_log)
            await self._session.commit()

    async def _is_already_processed(self, event: DataFileReadyEvent) -> bool:
        stmt = select(IngestionRunLogDB.id).where(
            IngestionRunLogDB.dataset == event.dataset,
            IngestionRunLogDB.run_id == event.run_id,
            IngestionRunLogDB.file_checksum == event.file_checksum,
            IngestionRunLogDB.status == "SUCCESS",
        )
        result = await self._session.exec(stmt)
        return result.first() is not None

    async def _process_dataset(self, event: DataFileReadyEvent) -> tuple[int, int]:
        """Read Parquet, create staging, load, and merge. Returns (loaded, merged)."""
        df = pd.read_parquet(event.path, engine="pyarrow")
        if df.empty:
            return 0, 0

        # Convert to dict and replace any pandas NA/NaN/NaT with None
        raw_records = df.to_dict(orient="records")
        records = [
            {k: (None if pd.isna(v) else v) for k, v in row.items()}
            for row in raw_records
        ]

        stg_table = f"stg_{event.dataset}"

        # Dispatch to specific merge strategy
        strategy = get_strategy(event.dataset)
        if not strategy:
            raise ValueError(f"Unknown dataset: {event.dataset}")

        await strategy.merge(self._session, stg_table, records)

        return len(records), len(records)  # assuming all merged
