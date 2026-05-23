"""Harvester FastStream application.

Composition root: builds the Kafka broker, binds the `FastStream` app,
then registers typed publishers and subscribers via side-effect imports.
The order matters: `broker` must exist before publisher/subscriber
modules are imported, because each decorator evaluates on module load.
"""

from __future__ import annotations

import logging

from faststream import FastStream
import typer

from common.messaging.broker import create_broker

logger = logging.getLogger(__name__)

broker = create_broker()
app = FastStream(broker, logger=logger)
cli_app = typer.Typer()

import harvester.publishers as publishers  # noqa: E402
from harvester.providers.alphavantage_provider import AlphaVantageProvider  # noqa: E402
from harvester.services.news_service import NewsService  # noqa: E402


@app.on_shutdown
async def on_shutdown() -> None:
    """Gracefully close the Kafka broker connection."""
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
        provider = AlphaVantageProvider()
        service = NewsService(provider, publishers.news_articles)
        await service.refresh_news(time_from=time_from, time_to=time_to)

    asyncio.run(main())


if __name__ == "__main__":
    cli_app()


import harvester.subscribers  # noqa: E402, F401 - decorator side-effect
