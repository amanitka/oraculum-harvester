"""Analyst FastStream application.

Composition root: builds the Kafka broker, binds the `FastStream` app,
then triggers subscriber registration via a side-effect import. The
order matters: `broker` must exist before the subscriber modules are
imported, because each `@broker.subscriber` decorator evaluates on
module load.
"""

from __future__ import annotations

import logging
import zlib

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from faststream import FastStream

from analyst.jobs.data_cleanup import create_data_cleanup_scheduler
from common.config import config
from common.messaging.broker import create_broker

logger = logging.getLogger(__name__)

_ACCESS_SAMPLE_MODULUS = 500
_HIGH_VOLUME_ACCESS_SUFFIXES: tuple[str, str] = (" - Received", " - Processed")
_ACCESS_TOPIC_LOGGER_NAMES: tuple[str, ...] = (
    config.topics.ticker,
    config.topics.income_statement,
    config.topics.balance_sheet,
    config.topics.cash_flow_statement,
    config.topics.share_price_batch,
)

broker = create_broker()
app = FastStream(broker, logger=logger)
_data_refresh_scheduler: AsyncIOScheduler | None = None
_data_cleanup_scheduler: AsyncIOScheduler | None = None

import analyst.subscribers  # noqa: E402, F401 - decorator side-effect


class _AccessLogSamplingFilter(logging.Filter):
    """Sample high-volume access INFO logs while keeping all other records."""

    def __init__(self, sample_modulus: int) -> None:
        super().__init__()
        self._sample_modulus = sample_modulus

    def filter(self, record: logging.LogRecord) -> bool:
        """Return whether one logging record should be emitted."""
        if record.levelno >= logging.WARNING:
            return True

        message = record.getMessage()
        if not message.endswith(_HIGH_VOLUME_ACCESS_SUFFIXES):
            return True

        encoded_message = message.encode("utf-8")
        return zlib.crc32(encoded_message) % self._sample_modulus == 0


def _install_access_log_sampling() -> None:
    """Install sampling filters for FastStream access loggers."""
    sample_filter = _AccessLogSamplingFilter(_ACCESS_SAMPLE_MODULUS)
    target_loggers = [
        logging.getLogger(),
        logging.getLogger("faststream"),
        logging.getLogger("faststream.access"),
        *(logging.getLogger(name) for name in _ACCESS_TOPIC_LOGGER_NAMES),
    ]

    for target_logger in target_loggers:
        has_sampling_filter = any(
            isinstance(existing_filter, _AccessLogSamplingFilter) for existing_filter in target_logger.filters
        )
        if has_sampling_filter:
            continue
        target_logger.addFilter(sample_filter)


@app.on_startup
async def _configure_access_log_sampling() -> None:
    """Configure sampled access logging before message consumption starts."""
    _install_access_log_sampling()
    logger.info("FastStream access-log sampling enabled [1/%d]", _ACCESS_SAMPLE_MODULUS)


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


@app.after_startup
async def _start_data_cleanup_jobs() -> None:
    """Start APScheduler-managed data cleanup jobs after broker startup."""
    global _data_cleanup_scheduler
    if _data_cleanup_scheduler and _data_cleanup_scheduler.running:
        return

    _data_cleanup_scheduler = create_data_cleanup_scheduler(
        config.harvester_data_path,
        cron_expression=config.analyst_cleanup.data_cleanup_cron,
        retention_days=config.analyst_cleanup.data_retention_days,
    )
    _data_cleanup_scheduler.start()
    logger.info("Data cleanup APScheduler started")


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


@app.on_shutdown
async def _stop_data_cleanup_jobs() -> None:
    """Stop the APScheduler-managed data cleanup jobs."""
    global _data_cleanup_scheduler
    if _data_cleanup_scheduler is None:
        return

    if _data_cleanup_scheduler.running:
        _data_cleanup_scheduler.shutdown(wait=False)
        logger.info("Data cleanup APScheduler stopped")

    _data_cleanup_scheduler = None


# @app.on_startup
async def _ensure_share_price_partitions() -> None:
    """Create any missing monthly partitions for t_share_price on startup."""
    from analyst.infrastructure.engine import EngineProvider
    from analyst.infrastructure.partition_manager import PartitionManager

    factory = await EngineProvider.session_factory()
    async with factory() as session:
        await PartitionManager.ensure_share_price_partitions(session)
        await session.commit()


# @app.on_startup
async def _ensure_news_partitions() -> None:
    """Create any missing yearly partitions for news tables on startup."""
    from analyst.infrastructure.engine import EngineProvider
    from analyst.infrastructure.partition_manager import PartitionManager

    factory = await EngineProvider.session_factory()
    async with factory() as session:
        await PartitionManager.ensure_news_partitions(session)
        await session.commit()
