"""Periodic data-refresh job functions for the analyst service.

Each public function publishes one category of harvester requests.
Cron scheduling and task creation are wired in the composition root
(``analyst.app``); this module stays pure and testable.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from typing import Any, Sequence

from croniter import croniter
from faststream.kafka import KafkaBroker

from common.config import config
from common.requests.balance_sheet import FetchBalanceSheetRequest
from common.requests.base import Request
from common.requests.cash_flow_statement import FetchCashFlowStatementRequest
from common.requests.income_statement import FetchIncomeStatementRequest
from common.requests.share_price import FetchSharePriceRequest
from common.requests.ticker import FetchTickerRequest

logger = logging.getLogger(__name__)

_MARKETS: tuple[str, ...] = ("us",)
_PRICE_SAFETY_WINDOW_DAYS: int = 7
_STATEMENT_VARIANTS: tuple[str, ...] = ("annual", "quarterly", "ttm")


def _build_price_requests() -> list[Request]:
    """Return one ``FetchSharePriceRequest`` per configured market."""
    from_date = date.today() - timedelta(days=_PRICE_SAFETY_WINDOW_DAYS)
    return [FetchSharePriceRequest(market=m, from_date=from_date) for m in _MARKETS]


def _build_fundamentals_requests() -> list[Request]:
    """Return income statement, balance sheet, and cash flow requests for all markets and variants."""
    requests: list[Request] = []
    for market in _MARKETS:
        for variant in _STATEMENT_VARIANTS:
            requests.append(FetchIncomeStatementRequest(market=market, variant=variant))
            requests.append(FetchBalanceSheetRequest(market=market, variant=variant))
            requests.append(FetchCashFlowStatementRequest(market=market, variant=variant))
    return requests


def _build_ticker_requests() -> list[Request]:
    """Return one ``FetchTickerRequest`` per configured market."""
    return [FetchTickerRequest(market=m) for m in _MARKETS]


async def _publish_all(broker: KafkaBroker, requests: Sequence[Request]) -> None:
    """Publish each request to the harvester request topic."""
    for request in requests:
        await broker.publish(request, topic=config.harvester_request_topic)
        logger.info(
            "Published %s [market=%s]",
            request.request_type,
            getattr(request, "market", "-"),
        )


async def _run_on_cron(
    cron: str,
    job: Callable[..., Awaitable[None]],
    *args: Any,
) -> None:
    """Sleep until the next cron fire time, run ``job``, then repeat."""
    while True:
        next_run: datetime = croniter(cron, datetime.now()).get_next(datetime)
        delay = (next_run - datetime.now()).total_seconds()
        logger.debug("Next run of %s in %.0f s (at %s)", job.__name__, delay, next_run)
        await asyncio.sleep(max(delay, 0))
        try:
            await job(*args)
        except Exception:
            logger.exception("Job %s failed; will retry at next scheduled time", job.__name__)


async def refresh_prices(broker: KafkaBroker) -> None:
    """Publish share price refresh requests for all configured markets."""
    await _publish_all(broker, _build_price_requests())


async def refresh_fundamentals(broker: KafkaBroker) -> None:
    """Publish income statement, balance sheet, and cash flow refresh requests."""
    await _publish_all(broker, _build_fundamentals_requests())


async def refresh_tickers(broker: KafkaBroker) -> None:
    """Publish ticker refresh requests for all configured markets."""
    await _publish_all(broker, _build_ticker_requests())
