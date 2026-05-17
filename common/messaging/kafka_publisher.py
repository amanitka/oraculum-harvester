import logging
from uuid import UUID

from common.config import config
from common.messaging.broker import create_broker
from common.requests.base import Request

logger = logging.getLogger(__name__)


class KafkaRequestPublisher:
    """
    A generic publisher for publishing request models to the correct Kafka topic.

    The topic is resolved dynamically based on the `request_type` field of the
    request model.
    """

    def __init__(self):
        self._topic_map = {
            "fetch_ticker": config.kafka.topics.harvester_request,
            "fetch_statements": config.kafka.topics.harvester_request,
            "fetch_share_prices": config.kafka.topics.harvester_request,
            "analyze_ticker": config.kafka.topics.analyst_request,
        }

    def publish_request(self, request: Request, key: str | UUID) -> None:
        """
        Publishes a request to the appropriate Kafka topic.

        Args:
            request: The request model to publish.
            key: The Kafka message key (typically a correlation ID).
        """
        topic = self._topic_map.get(request.request_type)
        if not topic:
            raise ValueError(f"No topic mapping found for request type: {request.request_type}")

        # This is a synchronous wrapper for now to fit the UI's current model.
        # The underlying broker is async, but we connect and disconnect per call.
        # For high-throughput scenarios, a shared, long-lived producer would be better.
        async def _publish():
            broker = create_broker()
            async with broker:
                await broker.publish(request, topic=topic, key=str(key))

        import asyncio
        asyncio.run(_publish())
