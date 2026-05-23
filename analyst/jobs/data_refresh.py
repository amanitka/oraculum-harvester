"""Periodic data-refresh jobs and scheduler wiring for the analyst service.

Each public refresh function publishes one category of harvester requests.
`create_data_refresh_scheduler` wires those jobs to APScheduler using the
cron expressions configured for analyst refresh automation.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable, Callable, Sequence
from datetime import date, timedelta, datetime, time

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from faststream.kafka import KafkaBroker

from common.config import config
from common.requests.balance_sheet import FetchBalanceSheetRequest
from common.requests.base import Request
from common.requests.cash_flow_statement import FetchCashFlowStatementRequest
from common.requests.income_statement import FetchIncomeStatementRequest
from common.requests.share_price import FetchSharePriceRequest
from common.requests.ticker import FetchTickerRequest
from common.requests.fetch_news import FetchNewsRequest
from analyst.infrastructure.engine import EngineProvider
from analyst.infrastructure.news_repository import NewsRepository

logger = logging.getLogger(__name__)

_MARKETS: tuple[str, ...] = ("us",)
_PRICE_SAFETY_WINDOW_DAYS: int = 7
_STATEMENT_VARIANTS: tuple[str, ...] = ("annual", "quarterly", "ttm")
_DEFAULT_MISFIRE_GRACE_SECONDS: int = 300
_REFRESH_PRICES_JOB_ID: str = "refresh_prices"
_REFRESH_FUNDAMENTALS_JOB_ID: str = "refresh_fundamentals"
_REFRESH_TICKERS_JOB_ID: str = "refresh_tickers"
_REFRESH_NEWS_JOB_ID: str = "refresh_news"
_JOB_DEFAULTS: dict[str, bool | int] = {
    "coalesce": True,
    "max_instances": 1,
    "misfire_grace_time": _DEFAULT_MISFIRE_GRACE_SECONDS,
}

type _RefreshJob = Callable[[KafkaBroker], Awaitable[None]]


def _build_price_requests() -> list[Request]:
    """Return one ``FetchSharePriceRequest`` per configured market."""
    from_date = date.today() - timedelta(days=_PRICE_SAFETY_WINDOW_DAYS)
    return [FetchSharePriceRequest(market=m, from_date=from_date) for m in _MARKETS]


def _build_fundamentals_requests() -> list[Request]:
    """Return fundamentals requests for all markets and variants."""
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


async def _build_news_requests() -> list[Request]:
    """Return one ``FetchNewsRequest`` for an incremental refresh."""
    factory = await EngineProvider.session_factory()
    async with factory() as session:
        repo = NewsRepository(session)
        max_time = await repo.get_max_time_published()

    if max_time:
        # Add a small buffer to avoid missing news due to clock skew
        from_datetime = max_time + timedelta(seconds=1)
    else:
        # If table is empty, start from today
        from_datetime = datetime.combine(date.today(), time.min)

    return [FetchNewsRequest(time_from=from_datetime.strftime("%Y%m%dT%H%M"))]


async def _publish_all(broker: KafkaBroker, requests: Sequence[Request]) -> None:
    """Publish each request to the harvester request topic."""
    for request in requests:
        await broker.publish(request, topic=config.harvester_request_topic)
        logger.info(
            "Published %s [market=%s]",
            request.request_type,
            getattr(request, "market", "-"),
        )


def _build_cron_trigger(cron_expression: str) -> CronTrigger:
    """Build one cron trigger from a five-field crontab expression."""
    return CronTrigger.from_crontab(cron_expression)


def _add_data_refresh_job(
    scheduler: AsyncIOScheduler,
    *,
    job_id: str,
    cron_expression: str,
    job: _RefreshJob,
    broker: KafkaBroker,
) -> None:
    """Register one periodic data-refresh publisher job on the scheduler."""
    scheduler.add_job(
        func=job,
        trigger=_build_cron_trigger(cron_expression),
        kwargs={"broker": broker},
        id=job_id,
        replace_existing=True,
    )


def create_data_refresh_scheduler(broker: KafkaBroker) -> AsyncIOScheduler:
    """Create an APScheduler instance for analyst data-refresh publishing jobs."""
    scheduler = AsyncIOScheduler(job_defaults=_JOB_DEFAULTS)
    refresh = config.analyst_refresh

    _add_data_refresh_job(
        scheduler,
        job_id=_REFRESH_TICKERS_JOB_ID,
        cron_expression=refresh.ticker_cron,
        job=refresh_tickers,
        broker=broker,
    )
    _add_data_refresh_job(
        scheduler,
        job_id=_REFRESH_PRICES_JOB_ID,
        cron_expression=refresh.price_cron,
        job=refresh_prices,
        broker=broker,
    )
    _add_data_refresh_job(
        scheduler,
        job_id=_REFRESH_FUNDAMENTALS_JOB_ID,
        cron_expression=refresh.fundamentals_cron,
        job=refresh_fundamentals,
        broker=broker,
    )
    _add_data_refresh_job(
        scheduler,
        job_id=_REFRESH_NEWS_JOB_ID,
        cron_expression=refresh.news_cron,
        job=refresh_news,
        broker=broker,
    )

    logger.info(
        "Data refresh jobs configured [prices=%s fundamentals=%s tickers=%s news=%s]",
        refresh.price_cron,
        refresh.fundamentals_cron,
        refresh.ticker_cron,
        refresh.news_cron,
    )
    return scheduler


async def refresh_prices(broker: KafkaBroker) -> None:
    """Publish share price refresh requests for all configured markets."""
    await _publish_all(broker, _build_price_requests())


async def refresh_fundamentals(broker: KafkaBroker) -> None:
    """Publish fundamentals refresh requests."""
    await _publish_all(broker, _build_fundamentals_requests())


async def refresh_tickers(broker: KafkaBroker) -> None:
    """Publish ticker refresh requests for all configured markets."""
    await _publish_all(broker, _build_ticker_requests())


async def refresh_news(broker: KafkaBroker) -> None:
    """Publish news and sentiment refresh requests."""
    requests = await _build_news_requests()
    await _publish_all(broker, requests)
