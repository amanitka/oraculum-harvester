"""Analyst FastStream application.

Composition root: builds the Kafka broker, binds the `FastStream` app,
then triggers subscriber registration via a side-effect import. The
order matters: `broker` must exist before the subscriber modules are
imported, because each `@broker.subscriber` decorator evaluates on
module load.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from faststream import FastStream

from common.messaging.broker import create_broker

logger = logging.getLogger(__name__)
logging.getLogger("faststream.access").setLevel(logging.WARNING)

broker = create_broker()
app = FastStream(broker, logger=logger)
_data_refresh_scheduler: AsyncIOScheduler | None = None

import analyst.subscribers  # noqa: E402, F401 - decorator side-effect


@app.after_startup
async def _start_data_refresh_jobs() -> None:
    """Start APScheduler-managed periodic data refresh jobs after broker startup."""
    global _data_refresh_scheduler
    if _data_refresh_scheduler and _data_refresh_scheduler.running:
        return

    from analyst.jobs.data_refresh import create_data_refresh_scheduler

    _data_refresh_scheduler = create_data_refresh_scheduler(broker)
    _data_refresh_scheduler.start()
    logger.info("Data refresh APScheduler started")


@app.on_shutdown
async def _stop_data_refresh_jobs() -> None:
    """Stop the APScheduler-managed periodic data refresh jobs."""
    global _data_refresh_scheduler
    if _data_refresh_scheduler is None:
        return

    if _data_refresh_scheduler.running:
        _data_refresh_scheduler.shutdown(wait=False)
        logger.info("Data refresh APScheduler stopped")

    _data_refresh_scheduler = None


@app.on_startup
async def _ensure_share_price_partitions() -> None:
    """Create any missing monthly partitions for t_share_price on startup."""
    from analyst.infrastructure.engine import EngineProvider
    from analyst.infrastructure.partition_manager import PartitionManager

    factory = await EngineProvider.session_factory()
    async with factory() as session:
        await PartitionManager.ensure_share_price_partitions(session)
        await session.commit()
