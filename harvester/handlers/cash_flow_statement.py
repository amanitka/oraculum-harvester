"""Handler for `FetchCashFlowStatementRequest`."""

from __future__ import annotations

import logging
from typing import Iterable, Type

from common import CashFlowStatement
from common.config import config
from common.messaging import KafkaProducerProvider
from common.requests import FetchCashFlowStatementRequest, Request
from harvester.handlers.base import RequestHandler
from harvester.providers import SimFinProvider

logger = logging.getLogger(__name__)


class CashFlowStatementRequestHandler(RequestHandler):
    """Streams SimFin cash flow statements for every requested industry template."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    @property
    def handles(self) -> Type[Request]:
        return FetchCashFlowStatementRequest

    def handle(self, request: Request) -> None:
        assert isinstance(request, FetchCashFlowStatementRequest)
        total = 0
        for template in request.templates:
            statements = self._provider.fetch_cash_flow_statement(
                template=template,
                variant=request.variant,
                market=request.market,
            )
            count = self._publish(statements)
            logger.info(
                "Published %d cash flow statements [cid=%s market=%s variant=%s template=%s]",
                count,
                request.correlation_id,
                request.market,
                request.variant,
                template,
            )
            total += count
        logger.info(
            "Cash flow statement fan-out complete: %d total rows [cid=%s]",
            total,
            request.correlation_id,
        )

    @staticmethod
    def _publish(cash_flow_statements: Iterable[CashFlowStatement]) -> int:
        producer = KafkaProducerProvider.get()
        topic = config.topics.cash_flow_statement
        count = 0
        for cash_flow_statement in cash_flow_statements:
            producer.send(
                topic,
                key=cash_flow_statement.composite_key,
                value=cash_flow_statement.model_dump(by_alias=False, mode="json"),
            )
            count += 1
        producer.flush()
        return count
