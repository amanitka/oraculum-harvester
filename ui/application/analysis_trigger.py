import logging
from datetime import date
from uuid import uuid4

from common.messaging.kafka_publisher import KafkaRequestPublisher
from common.requests.analyze_ticker import AnalyzeTickerRequest

logger = logging.getLogger(__name__)


class AnalysisTrigger:
    """
    A service for triggering ticker analysis workflows from the UI.
    """

    def __init__(self, publisher: KafkaRequestPublisher):
        self._publisher = publisher

    def trigger_analysis(self, ticker: str, market: str = "us") -> str:
        """
        Publishes an AnalyzeTickerRequest to Kafka and returns the correlation ID.

        Args:
            ticker: The ticker symbol to analyze.
            market: The market of the ticker (e.g., 'us').

        Returns:
            The correlation ID of the request.
        """
        correlation_id = uuid4()
        request = AnalyzeTickerRequest(
            ticker=ticker.upper().strip(),
            market=market.lower().strip(),
            as_of=date.today(),
            correlation_id=correlation_id,
        )

        logger.info(
            f"Publishing analysis request for {request.ticker}",
            extra={"cid": correlation_id, "ticker": request.ticker},
        )

        self._publisher.publish_request(
            request=request,
            key=str(correlation_id),
        )

        return str(correlation_id)
