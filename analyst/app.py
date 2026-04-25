"""Analyst FastStream application.

Composition root: builds the Kafka broker, binds the `FastStream` app,
then triggers subscriber registration via a side-effect import. The
order matters: `broker` must exist before the subscriber modules are
imported, because each `@broker.subscriber` decorator evaluates on
module load.
"""

from __future__ import annotations

import logging

from faststream import FastStream

from common.config import config
from common.messaging.broker import create_broker

logger = logging.getLogger(__name__)
logging.getLogger("faststream.access").setLevel(logging.WARNING)

broker = create_broker()
app = FastStream(broker, logger=logger)

import analyst.subscribers  # noqa: E402, F401 - decorator side-effect


@app.after_startup
async def _start_data_refresh_jobs() -> None:
    """Create cron-driven asyncio tasks for periodic data refresh after the broker connects."""
    import asyncio

    from analyst.jobs.data_refresh import _run_on_cron, refresh_fundamentals, refresh_prices, refresh_tickers

    refresh = config.analyst_refresh
    asyncio.create_task(_run_on_cron(refresh.ticker_cron, refresh_tickers, broker))
    asyncio.create_task(_run_on_cron(refresh.price_cron, refresh_prices, broker))
    asyncio.create_task(_run_on_cron(refresh.fundamentals_cron, refresh_fundamentals, broker))
    logger.info(
        "Data refresh tasks scheduled [prices=%s fundamentals=%s tickers=%s]",
        refresh.price_cron,
        refresh.fundamentals_cron,
        refresh.ticker_cron,
    )


@app.on_startup
async def _ensure_share_price_partitions() -> None:
    """Create any missing monthly partitions for t_share_price on startup."""
    from analyst.infrastructure.engine import EngineProvider
    from analyst.infrastructure.partition_manager import PartitionManager

    factory = await EngineProvider.session_factory()
    async with factory() as session:
        await PartitionManager.ensure_share_price_partitions(session)
        await session.commit()
