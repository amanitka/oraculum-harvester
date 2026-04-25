"""Shared FastStream Kafka broker factory.

Every service in the project talks to the same cluster. This factory
centralises wire configuration (bootstrap servers, durability,
serialization) so every producer/consumer inherits the same contract.
Consumer-group settings belong on each `@broker.subscriber`, not the
broker itself (FastStream 0.6+ API).
"""

from __future__ import annotations

from typing import Any, Optional

from faststream.kafka import KafkaBroker

from common.config import config


def _encode_key(key: Any) -> Optional[bytes]:
    if key is None:
        return None
    if isinstance(key, bytes):
        return key
    if isinstance(key, str):
        return key.encode("utf-8")
    return bytes(key)


def create_broker() -> KafkaBroker:
    """Build a broker bound to the shared Kafka cluster."""
    return KafkaBroker(
        ",".join(config.kafka_brokers),
        acks="all",
        linger_ms=20,
        key_serializer=_encode_key,
    )
