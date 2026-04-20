"""Harvester service entry point.

Consumes requests from `oraculum.harvester.request` and dispatches them
to typed handlers. One process handles requests sequentially; scale
horizontally by deploying more replicas in the same Kafka consumer
group (Kafka partitioning provides parallelism).
"""
from __future__ import annotations

import logging
from typing import Optional

from pydantic import ValidationError

from common.config import config
from common.messaging import KafkaConsumerProvider
from common.requests import Request, parse_request
from harvester.dispatcher import RequestDispatcher
from harvester.handlers import (
    RatioRequestHandler,
    StatementRequestHandler,
    TickerRequestHandler,
)
from harvester.providers import SimFinProvider

logger = logging.getLogger(__name__)


class HarvesterService:
    """Consumes harvester requests and dispatches them."""

    def __init__(
        self,
        dispatcher: RequestDispatcher,
        topic: Optional[str] = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._topic = topic or config.harvester_request_topic

    def run(self) -> None:
        consumer = KafkaConsumerProvider.get(self._topic)
        logger.info("Listening on %s", self._topic)
        for message in consumer:
            self._process(message)
            consumer.commit()

    def _process(self, message) -> None:
        request = self._safe_parse(message)
        if request is None:
            return
        self._safe_dispatch(request)

    @staticmethod
    def _safe_parse(message) -> Optional[Request]:
        try:
            return parse_request(message.value)
        except ValidationError as exc:
            logger.error(
                "Invalid request at offset=%s: %s", message.offset, exc
            )
        except Exception:  # noqa: BLE001 - supervisor boundary
            logger.exception(
                "Unexpected parse error at offset=%s", message.offset
            )
        return None

    def _safe_dispatch(self, request: Request) -> None:
        try:
            self._dispatcher.dispatch(request)
        except Exception:  # noqa: BLE001 - supervisor boundary; log & commit
            logger.exception(
                "Handler failed for request_type=%s cid=%s",
                request.request_type,
                request.correlation_id,
            )


def build_default_service() -> HarvesterService:
    """Composition root: wire provider, handlers, dispatcher, and service."""
    provider = SimFinProvider()
    dispatcher = RequestDispatcher(
        [
            TickerRequestHandler(provider),
            StatementRequestHandler(),
            RatioRequestHandler(),
        ]
    )
    return HarvesterService(dispatcher)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    build_default_service().run()


if __name__ == "__main__":
    main()
