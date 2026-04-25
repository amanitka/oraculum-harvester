"""Subscriber for the share price batch topic."""

from __future__ import annotations

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session
from analyst.infrastructure.repositories.share_price import SharePriceRepository
from common.config import config
from common.domain.share_price import SharePriceBatch

logger = logging.getLogger(__name__)


@broker.subscriber(
    config.topics.share_price_batch,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_share_price_batch(
    batch: SharePriceBatch, session: AsyncSession = Session()
) -> None:
    """Persist an incoming share price batch via bulk upsert."""
    count = await SharePriceRepository(session).bulk_upsert(batch)
    logger.info(
        "Upserted %d share price rows [market=%s from_date=%s]",
        count,
        batch.market,
        batch.from_date,
    )
