"""Subscriber for the ticker topic."""

from __future__ import annotations

import logging

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session
from analyst.infrastructure.repositories.ticker import TickerRepository
from common.config import config
from common.domain.ticker import Ticker

logger = logging.getLogger(__name__)


@broker.subscriber(
    config.topics.ticker,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_ticker(ticker: Ticker, session: AsyncSession = Session()) -> None:
    """Persist an incoming ticker event."""
    await TickerRepository(session).upsert(ticker)
    logger.info("Upserted ticker %s (%s)", ticker.symbol, ticker.market)
