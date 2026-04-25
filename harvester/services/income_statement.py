"""Fetch + publish income statements across industry templates."""

from __future__ import annotations

import asyncio
import logging

from common.domain import IncomeStatementTemplate
from common.requests import FetchIncomeStatementRequest
from harvester.providers import SimFinProvider
from harvester.publishers import income_statement as income_statement_publisher

logger = logging.getLogger(__name__)


class IncomeStatementService:
    """Streams SimFin income statements for every requested industry template."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchIncomeStatementRequest) -> None:
        """Fan out one request over all templates; publish each row."""
        total = 0
        for template in request.templates:
            count = await self._process_template(request, template)
            total += count
        logger.info(
            "Income statement fan-out complete: %d total rows [cid=%s]",
            total,
            request.correlation_id,
        )

    async def _process_template(
        self,
        request: FetchIncomeStatementRequest,
        template: IncomeStatementTemplate,
    ) -> int:
        statements = await asyncio.to_thread(
            lambda: list(
                self._provider.fetch_income(
                    template=template,
                    variant=request.variant,
                    market=request.market,
                )
            )
        )
        for statement in statements:
            await income_statement_publisher.publish(
                statement, key=statement.composite_key
            )
        logger.info(
            "Published %d income statements [cid=%s market=%s variant=%s template=%s]",
            len(statements),
            request.correlation_id,
            request.market,
            request.variant,
            template,
        )
        return len(statements)
