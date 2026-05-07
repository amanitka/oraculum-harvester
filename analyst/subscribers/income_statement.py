"""Subscriber for the income statement topic."""

from __future__ import annotations

import logging
import zlib

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session
from analyst.infrastructure.repositories.income_statement import (
    IncomeStatementRepository,
)
from common.config import config
from common.domain.income_statement import IncomeStatement

logger = logging.getLogger(__name__)

_SAMPLED_INFO_LOG_MODULUS = 500


def _should_emit_sample_log(statement: IncomeStatement) -> bool:
    """Return whether this statement should emit an informational sample log."""
    encoded_key = statement.composite_key.encode("utf-8")
    return zlib.crc32(encoded_key) % _SAMPLED_INFO_LOG_MODULUS == 0


@broker.subscriber(
    config.topics.income_statement,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_income_statement(
    statement: IncomeStatement,
    session: AsyncSession = Session(),
) -> None:
    """Persist an incoming income statement event."""
    await IncomeStatementRepository(session).upsert(statement)
    if _should_emit_sample_log(statement):
        logger.info("Upserted sampled income statement %s", statement.composite_key)
