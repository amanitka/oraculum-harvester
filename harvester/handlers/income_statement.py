"""Handler for `FetchIncomeStatementRequest`."""

from __future__ import annotations

import logging
from typing import Iterable, Type

from common import IncomeStatement
from common.config import config
from common.messaging import KafkaProducerProvider
from common.requests import FetchIncomeStatementRequest, Request
from harvester.handlers.base import RequestHandler
from harvester.providers import SimFinProvider

logger = logging.getLogger(__name__)


class IncomeStatementRequestHandler(RequestHandler):
    """Streams SimFin income statements for every requested industry template."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    @property
    def handles(self) -> Type[Request]:
        return FetchIncomeStatementRequest

    def handle(self, request: Request) -> None:
        assert isinstance(request, FetchIncomeStatementRequest)
        total = 0
        for template in request.templates:
            statements = self._provider.fetch_income(
                template=template,
                variant=request.variant,
                market=request.market,
            )
            count = self._publish(statements)
            logger.info(
                "Published %d income statements [cid=%s market=%s variant=%s template=%s]",
                count,
                request.correlation_id,
                request.market,
                request.variant,
                template,
            )
            total += count
        logger.info(
            "Income statement fan-out complete: %d total rows [cid=%s]",
            total,
            request.correlation_id,
        )

    @staticmethod
    def _publish(income_statements: Iterable[IncomeStatement]) -> int:
        producer = KafkaProducerProvider.get()
        topic = config.topics.income_statement
        count = 0
        for income_statement in income_statements:
            producer.send(
                topic,
                key=income_statement.composite_key,
                value=income_statement.model_dump(by_alias=False, mode="json"),
            )
            count += 1
        producer.flush()
        return count
