"""Subscriber for the balance sheet topic."""

from __future__ import annotations

import logging
import zlib

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session
from analyst.infrastructure.repositories.balance_sheet import BalanceSheetRepository
from common.config import config
from common.domain.balance_sheet import BalanceSheet

logger = logging.getLogger(__name__)

_SAMPLED_INFO_LOG_MODULUS = 500


def _should_emit_sample_log(statement: BalanceSheet) -> bool:
    """Return whether this statement should emit an informational sample log."""
    encoded_key = statement.composite_key.encode("utf-8")
    return zlib.crc32(encoded_key) % _SAMPLED_INFO_LOG_MODULUS == 0


@broker.subscriber(
    config.topics.balance_sheet,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_balance_sheet(
    statement: BalanceSheet,
    session: AsyncSession = Session(),
) -> None:
    """Persist an incoming balance sheet event."""
    await BalanceSheetRepository(session).upsert(statement)
    if _should_emit_sample_log(statement):
        logger.info("Upserted sampled balance sheet %s", statement.composite_key)
