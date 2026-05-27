"""Subscriber for data_file_ready events."""

from __future__ import annotations

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.dependencies import Session
from analyst.infrastructure.parquet_loader import ParquetLoader
from common.domain.data_file_ready import DataFileReadyEvent

logger = logging.getLogger(__name__)


# @broker.subscriber(
#    config.topics.data_file_ready,
#    group_id=config.analyst_consumer_group,
#    auto_offset_reset="earliest",
# )
async def on_data_file_ready(event: DataFileReadyEvent, session: AsyncSession = Session()) -> None:
    """Consume a data_file_ready event and load its Parquet payload into PostgreSQL."""
    logger.info("Received data_file_ready for dataset=%s run_id=%s", event.dataset, event.run_id)

    loader = ParquetLoader(session)
    await loader.load(event)

    logger.info(
        "Successfully processed data_file_ready for dataset=%s run_id=%s",
        event.dataset,
        event.run_id,
    )
