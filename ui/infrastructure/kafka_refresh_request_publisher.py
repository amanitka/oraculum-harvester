"""Kafka adapter for publishing manual refresh requests."""

from __future__ import annotations

from common.config import config
from common.messaging.broker import create_broker
from common.requests.base import Request
from ui.application.ports import RefreshRequestPublisher


class KafkaRefreshRequestPublisher(RefreshRequestPublisher):
    """Publish refresh requests to the shared harvester-request topic."""

    async def publish(self, request: Request) -> None:
        """Publish one request to Kafka using the shared broker settings."""
        broker = create_broker()
        async with broker:
            await broker.publish(request, topic=config.harvester_request_topic)
