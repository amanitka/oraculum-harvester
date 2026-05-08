"""Harvester FastStream application.

Composition root: builds the Kafka broker, binds the `FastStream` app,
then registers typed publishers and subscribers via side-effect imports.
The order matters: `broker` must exist before publisher/subscriber
modules are imported, because each decorator evaluates on module load.
"""

from __future__ import annotations

import logging

from faststream import FastStream

from common.messaging.broker import create_broker

logger = logging.getLogger(__name__)

broker = create_broker()
app = FastStream(broker, logger=logger)


@app.on_shutdown
async def on_shutdown() -> None:
    """Gracefully close the Kafka broker connection."""
    await broker.close()
    logger.info("Kafka broker closed gracefully.")


import harvester.publishers  # noqa: E402, F401 - decorator side-effect
import harvester.subscribers  # noqa: E402, F401 - decorator side-effect
