"""Fetch + publish cash flow statements across industry templates."""

from __future__ import annotations

import asyncio
import logging

from common.domain import CashFlowStatementTemplate
from common.requests import FetchCashFlowStatementRequest
from harvester.providers import SimFinProvider
from harvester.publishers import cash_flow_statement as cash_flow_publisher

logger = logging.getLogger(__name__)


class CashFlowStatementService:
    """Streams SimFin cash flow statements for every requested industry template."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(
        self, request: FetchCashFlowStatementRequest
    ) -> None:
        """Fan out one request over all templates; publish each row."""
        total = 0
        for template in request.templates:
            count = await self._process_template(request, template)
            total += count
        logger.info(
            "Cash flow statement fan-out complete: %d total rows [cid=%s]",
            total,
            request.correlation_id,
        )

    async def _process_template(
        self,
        request: FetchCashFlowStatementRequest,
        template: CashFlowStatementTemplate,
    ) -> int:
        statements = await asyncio.to_thread(
            lambda: list(
                self._provider.fetch_cash_flow_statement(
                    template=template,
                    variant=request.variant,
                    market=request.market,
                )
            )
        )
        for statement in statements:
            await cash_flow_publisher.publish(
                statement, key=statement.composite_key
            )
        logger.info(
            "Published %d cash flow statements [cid=%s market=%s variant=%s template=%s]",
            len(statements),
            request.correlation_id,
            request.market,
            request.variant,
            template,
        )
        return len(statements)
