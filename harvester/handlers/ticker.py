"""Handler for `FetchTickerRequest`."""
from __future__ import annotations

import logging
from typing import Iterable, Type

from common import Ticker
from common.config import config
from common.messaging import KafkaProducerProvider
from common.requests import FetchTickerRequest, Request
from harvester.handlers.base import RequestHandler
from harvester.providers import SimFinProvider

logger = logging.getLogger(__name__)


class TickerRequestHandler(RequestHandler):
    """Streams tickers from SimFin onto the ticker topic."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    @property
    def handles(self) -> Type[Request]:
        return FetchTickerRequest

    def handle(self, request: Request) -> None:
        assert isinstance(request, FetchTickerRequest)
        count = self._publish(self._provider.fetch_tickers(market=request.market))
        logger.info(
            "Published %d tickers [cid=%s market=%s]",
            count,
            request.correlation_id,
            request.market,
        )

    @staticmethod
    def _publish(tickers: Iterable[Ticker]) -> int:
        producer = KafkaProducerProvider.get()
        topic = config.topics.ticker
        count = 0
        for ticker in tickers:
            producer.send(
                topic,
                key=ticker.symbol,
                value=ticker.model_dump(by_alias=False, mode="json"),
            )
            count += 1
        producer.flush()
        return count
