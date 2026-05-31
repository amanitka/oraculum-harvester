"""Subscriber for `oraculum.harvester.request`.

Dispatches the discriminated `AnyRequest` union to its owning domain
service via structural pattern matching. Adding a new request type is a
two-step change: extend the union in `common.requests`, then add a
`case` here plus a new service.
"""

from __future__ import annotations

import logging

from common.config import config
from common.requests import (
    AnyRequest,
    FetchBalanceSheetRequest,
    FetchCashFlowStatementRequest,
    FetchCompanyRequest,
    FetchIncomeStatementRequest,
    FetchSharePriceRequest,
    FetchMarketRequest,
    FetchIndustryRequest,
    FetchNewsRequest,
)
from harvester.app import broker
from harvester.providers.simfin_provider import SimFinProvider
from harvester.providers.market import MarketProvider
from harvester.providers.industry import IndustryProvider
from harvester.providers.alphavantage_provider import AlphaVantageProvider
from harvester.services import (
    BalanceSheetService,
    CashFlowStatementService,
    CompanyService,
    IncomeStatementService,
    SharePriceService,
)
from harvester.services.market import MarketService
from harvester.services.industry import IndustryService
from harvester.services.news_service import NewsService
import harvester.publishers as publishers

logger = logging.getLogger(__name__)

_provider = SimFinProvider()
_company_service = CompanyService(_provider)
_income_service = IncomeStatementService(_provider)
_balance_service = BalanceSheetService(_provider)
_cash_flow_service = CashFlowStatementService(_provider)
_share_price_service = SharePriceService(_provider)

_market_service = MarketService(MarketProvider())
_industry_service = IndustryService(IndustryProvider())

_news_service = NewsService(AlphaVantageProvider(), publishers.news_articles)


@broker.subscriber(
    config.harvester_request_topic,
    group_id=config.harvester_consumer_group,
    auto_offset_reset="earliest",
)
async def on_request(request: AnyRequest) -> None:
    """Dispatch an incoming fetch request to its owning domain service."""
    match request:
        case FetchCompanyRequest():
            await _company_service.fetch_and_publish(request)
        case FetchIncomeStatementRequest():
            await _income_service.fetch_and_publish(request)
        case FetchBalanceSheetRequest():
            await _balance_service.fetch_and_publish(request)
        case FetchCashFlowStatementRequest():
            await _cash_flow_service.fetch_and_publish(request)
        case FetchSharePriceRequest():
            await _share_price_service.fetch_and_publish(request)
        case FetchMarketRequest():
            await _market_service.fetch_and_publish(request)
        case FetchIndustryRequest():
            await _industry_service.fetch_and_publish(request)
        case FetchNewsRequest():
            await _news_service.refresh_news(time_from=request.time_from, time_to=request.time_to)
