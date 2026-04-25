"""Subscriber for the ticker topic."""

from __future__ import annotations

import logging
import zlib

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session
from analyst.infrastructure.repositories.ticker import TickerRepository
from common.config import config
from common.domain.ticker import Ticker

logger = logging.getLogger(__name__)

_SAMPLED_INFO_LOG_MODULUS = 500


def _should_emit_sample_log(ticker: Ticker) -> bool:
    """Return whether this ticker should emit an informational sample log."""
    encoded_key = f"{ticker.symbol}:{ticker.market}".encode("utf-8")
    return zlib.crc32(encoded_key) % _SAMPLED_INFO_LOG_MODULUS == 0


@broker.subscriber(
    config.topics.ticker,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_ticker(ticker: Ticker, session: AsyncSession = Session()) -> None:
    """Persist an incoming ticker event."""
    await TickerRepository(session).upsert(ticker)
    if _should_emit_sample_log(ticker):
        logger.info("Upserted sampled ticker %s (%s)", ticker.symbol, ticker.market)
