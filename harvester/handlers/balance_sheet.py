"""Handler for `FetchBalanceSheetRequest`."""
from __future__ import annotations

import logging
from typing import Iterable, Type

from common import BalanceSheet
from common.config import config
from common.messaging import KafkaProducerProvider
from common.requests import FetchBalanceSheetRequest, Request
from harvester.handlers.base import RequestHandler
from harvester.providers import SimFinProvider

logger = logging.getLogger(__name__)


class BalanceSheetRequestHandler(RequestHandler):
    """Streams SimFin balance sheets for every requested industry template."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    @property
    def handles(self) -> Type[Request]:
        return FetchBalanceSheetRequest

    def handle(self, request: Request) -> None:
        assert isinstance(request, FetchBalanceSheetRequest)
        total = 0
        for template in request.templates:
            statements = self._provider.fetch_balance_sheet(
                template=template,
                variant=request.variant,
                market=request.market,
            )
            count = self._publish(statements)
            logger.info(
                "Published %d balance sheets [cid=%s market=%s variant=%s template=%s]",
                count,
                request.correlation_id,
                request.market,
                request.variant,
                template,
            )
            total += count
        logger.info(
            "Balance sheet fan-out complete: %d total rows [cid=%s]",
            total,
            request.correlation_id,
        )

    @staticmethod
    def _publish(balance_sheets: Iterable[BalanceSheet]) -> int:
        producer = KafkaProducerProvider.get()
        topic = config.topics.balance_sheet
        count = 0
        for balance_sheet in balance_sheets:
            producer.send(
                topic,
                key=balance_sheet.composite_key,
                value=balance_sheet.model_dump(by_alias=False, mode="json"),
            )
            count += 1
        producer.flush()
        return count
