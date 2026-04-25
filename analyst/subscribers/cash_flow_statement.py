"""Subscriber for the cash flow statement topic."""

from __future__ import annotations

import logging
import zlib

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session
from analyst.infrastructure.repositories.cash_flow_statement import CashFlowStatementRepository
from common.config import config
from common.domain.cash_flow_statement import CashFlowStatement

logger = logging.getLogger(__name__)

_SAMPLED_INFO_LOG_MODULUS = 500


def _should_emit_sample_log(statement: CashFlowStatement) -> bool:
    """Return whether this statement should emit an informational sample log."""
    encoded_key = statement.composite_key.encode("utf-8")
    return zlib.crc32(encoded_key) % _SAMPLED_INFO_LOG_MODULUS == 0


@broker.subscriber(
    config.topics.cash_flow_statement,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_cash_flow_statement(
    statement: CashFlowStatement,
    session: AsyncSession = Session(),
) -> None:
    """Persist an incoming cash flow statement event."""
    await CashFlowStatementRepository(session).upsert(statement)
    if _should_emit_sample_log(statement):
        logger.info(
            "Upserted sampled cash flow statement %s",
            statement.composite_key,
        )
