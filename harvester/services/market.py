import logging

from common.config import config
from common.requests.fetch_market import FetchMarketRequest
from harvester.app import broker
from harvester.providers.simfin_provider import SimFinProvider

logger = logging.getLogger(__name__)


class MarketService:
    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchMarketRequest) -> None:
        logger.info(
            f"Processing market fetch request {request.correlation_id}",
            extra={"cid": request.correlation_id},
        )

        try:
            markets = list(self._provider.fetch_markets())
            if not markets:
                logger.warning("No markets found.", extra={"cid": request.correlation_id})
                return

            # For small static tables like market, we can just publish them all at once.
            # No need for Parquet batches.
            for m in markets:
                await broker.publish(
                    m,
                    topic=config.topics.market,
                    key=m.market_id,
                )

            logger.info(
                f"Published {len(markets)} markets to Kafka.",
                extra={"cid": request.correlation_id},
            )
        except Exception as e:
            logger.exception(
                f"Failed to process market request: {e}",
                extra={"cid": request.correlation_id},
            )
