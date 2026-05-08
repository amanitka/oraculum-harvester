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
    FetchIncomeStatementRequest,
    FetchSharePriceRequest,
    FetchTickerRequest,
)
from harvester.app import broker
from harvester.providers import SimFinProvider
from harvester.services import (
    BalanceSheetService,
    CashFlowStatementService,
    IncomeStatementService,
    SharePriceService,
    TickerService,
)

logger = logging.getLogger(__name__)

_provider = SimFinProvider()
_ticker_service = TickerService(_provider)
_income_service = IncomeStatementService(_provider)
_balance_service = BalanceSheetService(_provider)
_cash_flow_service = CashFlowStatementService(_provider)
_share_price_service = SharePriceService(_provider)


@broker.subscriber(
    config.harvester_request_topic,
    group_id=config.harvester_consumer_group,
    auto_offset_reset="earliest",
)
async def on_request(request: AnyRequest) -> None:
    """Dispatch an incoming fetch request to its owning domain service."""
    match request:
        case FetchTickerRequest():
            await _ticker_service.fetch_and_publish(request)
        case FetchIncomeStatementRequest():
            await _income_service.fetch_and_publish(request)
        case FetchBalanceSheetRequest():
            await _balance_service.fetch_and_publish(request)
        case FetchCashFlowStatementRequest():
            await _cash_flow_service.fetch_and_publish(request)
        case FetchSharePriceRequest():
            await _share_price_service.fetch_and_publish(request)
