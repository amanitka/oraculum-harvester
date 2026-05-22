import logging

from common.config import config
from common.requests.fetch_industry import FetchIndustryRequest
from harvester.app import broker
from harvester.providers.industry import IndustryProvider

logger = logging.getLogger(__name__)


class IndustryService:
    def __init__(self, provider: IndustryProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchIndustryRequest) -> None:
        logger.info(
            f"Processing industry fetch request {request.correlation_id}",
            extra={"cid": request.correlation_id},
        )

        try:
            industries = list(self._provider.fetch_industries())
            if not industries:
                logger.warning("No industries found.", extra={"cid": request.correlation_id})
                return

            # For small static tables like industry, we can just publish them all at once.
            for ind in industries:
                await broker.publish(
                    ind,
                    topic=config.topics.industry,
                    key=ind.industry_id,
                )

            logger.info(
                f"Published {len(industries)} industries to Kafka.",
                extra={"cid": request.correlation_id},
            )
        except Exception as e:
            logger.exception(
                f"Failed to process industry request: {e}",
                extra={"cid": request.correlation_id},
            )
