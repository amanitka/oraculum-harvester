"""Shared FastStream Kafka broker factory.

Every service in the project talks to the same cluster. This factory
centralises the wire configuration (bootstrap servers). Consumer-group
settings belong on each `@broker.subscriber`, not the broker itself
(FastStream 0.6+ API).
"""

from __future__ import annotations

from faststream.kafka import KafkaBroker

from common.config import config


def create_broker() -> KafkaBroker:
    """Build a broker bound to the shared Kafka cluster."""
    return KafkaBroker(",".join(config.kafka_brokers))
