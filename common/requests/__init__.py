"""Pydantic schemas for the uniform command topic."""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field

from common.requests.balance_sheet import FetchBalanceSheetRequest
from common.requests.base import Request
from common.requests.cash_flow_statement import FetchCashFlowStatementRequest
from common.requests.company import FetchCompanyRequest
from common.requests.income_statement import FetchIncomeStatementRequest
from common.requests.share_price import FetchSharePriceRequest
from common.requests.fetch_market import FetchMarketRequest
from common.requests.fetch_industry import FetchIndustryRequest

# Discriminated union of all possible refresh requests.
# Adding a new command means adding it to this tuple so FastStream
# correctly deserializes the JSON payload into the matching model.
AnyRequest = Annotated[
    Union[
        FetchCompanyRequest,
        FetchIncomeStatementRequest,
        FetchBalanceSheetRequest,
        FetchCashFlowStatementRequest,
        FetchSharePriceRequest,
        FetchMarketRequest,
        FetchIndustryRequest,
    ],
    Field(discriminator="request_type"),
]

__all__ = [
    "AnyRequest",
    "FetchBalanceSheetRequest",
    "FetchCashFlowStatementRequest",
    "FetchCompanyRequest",
    "FetchIncomeStatementRequest",
    "FetchSharePriceRequest",
    "FetchMarketRequest",
    "FetchIndustryRequest",
    "Request",
]
