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
    FetchInsiderTransactionsRequest,
    FetchSecDocumentsRequest,
)
from harvester.app import broker
from harvester.providers.simfin_provider import SimFinProvider
from harvester.providers.openinsider_provider import OpenInsiderProvider
from harvester.providers.sec_provider import SecProvider
from harvester.services import (
    BalanceSheetService,
    CashFlowStatementService,
    CompanyService,
    IncomeStatementService,
    SharePriceService,
    InsiderTransactionService,
)
from harvester.services.market import MarketService
from harvester.services.industry import IndustryService
from harvester.services.sec_document import SecDocumentService

logger = logging.getLogger(__name__)

_provider = SimFinProvider()
_company_service = CompanyService(_provider)
_income_service = IncomeStatementService(_provider)
_balance_service = BalanceSheetService(_provider)
_cash_flow_service = CashFlowStatementService(_provider)
_share_price_service = SharePriceService(_provider)

_market_service = MarketService(_provider)
_industry_service = IndustryService(_provider)

_openinsider_provider = OpenInsiderProvider()
_insider_service = InsiderTransactionService(_openinsider_provider)

_sec_provider = SecProvider()
_sec_document_service = SecDocumentService(_sec_provider)


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
        case FetchInsiderTransactionsRequest():
            await _insider_service.fetch_and_publish(request)
        case FetchSecDocumentsRequest():
            await _sec_document_service.fetch_sec_documents(request)
