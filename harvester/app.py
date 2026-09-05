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
from harvester.services.cleanup import HarvesterTempCleanup

logger = logging.getLogger(__name__)

broker = create_broker()
app = FastStream(broker, logger=logger)
cli_app = typer.Typer()
temp_cleanup = HarvesterTempCleanup()

import harvester.publishers as publishers  # noqa: E402, F401


@app.on_startup
async def on_startup() -> None:
    """Start background cleanup scheduler."""
    temp_cleanup.start()


@app.on_shutdown
async def on_shutdown() -> None:
    """Gracefully cancel background cleanup and close the Kafka broker connection."""
    temp_cleanup.stop()
    await broker.stop()
    logger.info("Kafka broker closed gracefully.")


if __name__ == "__main__":
    cli_app()


import harvester.subscribers  # noqa: E402, F401 - decorator side-effect
