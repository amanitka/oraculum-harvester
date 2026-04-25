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

from common.messaging.broker import create_broker

logger = logging.getLogger(__name__)
logging.getLogger("faststream.access").setLevel(logging.WARNING)

broker = create_broker()
app = FastStream(broker, logger=logger)

import analyst.subscribers  # noqa: E402, F401 - decorator side-effect
