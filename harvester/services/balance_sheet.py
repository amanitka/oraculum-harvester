"""Fetch + publish balance sheets across industry templates."""

from __future__ import annotations

import asyncio
import logging

from common.domain import BalanceSheetTemplate
from common.requests import FetchBalanceSheetRequest
from harvester.providers import SimFinProvider
from harvester.publishers import balance_sheet as balance_sheet_publisher

logger = logging.getLogger(__name__)


class BalanceSheetService:
    """Streams SimFin balance sheets for every requested industry template."""

    def __init__(self, provider: SimFinProvider) -> None:
        self._provider = provider

    async def fetch_and_publish(self, request: FetchBalanceSheetRequest) -> None:
        """Fan out one request over all templates; publish each row."""
        total = 0
        for template in request.templates:
            count = await self._process_template(request, template)
            total += count
        logger.info(
            "Balance sheet fan-out complete: %d total rows [cid=%s]",
            total,
            request.correlation_id,
        )

    async def _process_template(
        self,
        request: FetchBalanceSheetRequest,
        template: BalanceSheetTemplate,
    ) -> int:
        statements = await asyncio.to_thread(
            lambda: list(
                self._provider.fetch_balance_sheet(
                    template=template,
                    variant=request.variant,
                    market=request.market,
                )
            )
        )
        for statement in statements:
            await balance_sheet_publisher.publish(
                statement, key=statement.composite_key
            )
        logger.info(
            "Published %d balance sheets [cid=%s market=%s variant=%s template=%s]",
            len(statements),
            request.correlation_id,
            request.market,
            request.variant,
            template,
        )
        return len(statements)
