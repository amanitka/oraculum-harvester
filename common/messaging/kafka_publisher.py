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
            # Harvester requests go to a single topic
            "fetch_ticker": config.harvester_request_topic,
            "fetch_statements": config.harvester_request_topic,
            "fetch_income_statement": config.harvester_request_topic,
            "fetch_balance_sheet": config.harvester_request_topic,
            "fetch_cash_flow_statement": config.harvester_request_topic,
            "fetch_share_price": config.harvester_request_topic,
            "fetch_market": config.harvester_request_topic,
            "fetch_industry": config.harvester_request_topic,
            "fetch_news": config.harvester_request_topic,
            # Analyst requests go to the analyst topic
            "analyze_ticker": config.topics.analyst_request,
        }

    def publish_request(self, request: Request, key: str | UUID | None = None) -> None:
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
                await broker.publish(request, topic=topic, key=str(key) if key else None)

        import asyncio

        asyncio.run(_publish())

    async def publish(self, request: Request) -> None:
        """
        Async publisher to satisfy the RefreshRequestPublisher protocol used by RefreshService.
        """
        topic = self._topic_map.get(request.request_type)
        if not topic:
            raise ValueError(f"No topic mapping found for request type: {request.request_type}")

        broker = create_broker()
        async with broker:
            await broker.publish(request, topic=topic)