"""Harvester FastStream application.

Composition root: builds the Kafka broker, binds the `FastStream` app,
then registers typed publishers and subscribers via side-effect imports.
The order matters: `broker` must exist before publisher/subscriber
modules are imported, because each decorator evaluates on module load.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from faststream import FastStream
import typer

from common.messaging.broker import create_broker
from harvester.jobs.news_jobs import create_news_refresh_scheduler
from harvester.providers.alphavantage_provider import AlphavantageProvider
from harvester.services.news_service import NewsService
import harvester.publishers as publishers

logger = logging.getLogger(__name__)

broker = create_broker()
app = FastStream(broker, logger=logger)
cli_app = typer.Typer()

_news_refresh_scheduler: AsyncIOScheduler | None = None


@app.on_startup
async def _start_news_refresh_jobs() -> None:
    """Start APScheduler-managed periodic news refresh jobs after broker startup."""
    global _news_refresh_scheduler
    if _news_refresh_scheduler and _news_refresh_scheduler.running:
        return

    provider = AlphavantageProvider()
    service = NewsService(provider, publishers.news_articles)
    _news_refresh_scheduler = create_news_refresh_scheduler(service)
    _news_refresh_scheduler.start()
    logger.info("News refresh APScheduler started")


@app.on_shutdown
async def on_shutdown() -> None:
    """Gracefully close the Kafka broker connection."""
    global _news_refresh_scheduler
    if _news_refresh_scheduler and _news_refresh_scheduler.running:
        _news_refresh_scheduler.shutdown(wait=False)
        logger.info("News refresh APScheduler stopped")

    await broker.close()
    logger.info("Kafka broker closed gracefully.")


@cli_app.command()
def refresh_news(
    time_from: str = typer.Option(None, help="Start time for the news query (YYYYMMDDTHHMM)"),
    time_to: str = typer.Option(None, help="End time for the news query (YYYYMMDDTHHMM)"),
) -> None:
    """Manually trigger a refresh of news and sentiment data."""
    import asyncio

    async def main() -> None:
        provider = AlphavantageProvider()
        service = NewsService(provider, publishers.news_articles)
        await service.refresh_news(time_from=time_from, time_to=time_to)

    asyncio.run(main())


if __name__ == "__main__":
    cli_app()


import harvester.publishers  # noqa: E402, F401 - decorator side-effect
import harvester.subscribers  # noqa: E402, F401 - decorator side-effect
