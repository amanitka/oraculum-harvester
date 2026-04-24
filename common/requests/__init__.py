"""Discriminated union of all harvester requests + a parser."""

from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field, TypeAdapter, ValidationError

from common.requests.base import Request
from common.requests.ratio import FetchRatioRequest
from common.requests.income_statement import FetchIncomeStatementRequest
from common.requests.balance_sheet import FetchBalanceSheetRequest
from common.requests.cash_flow_statement import FetchCashFlowStatementRequest
from common.requests.ticker import FetchTickerRequest

AnyRequest = Annotated[
    Union[
        FetchTickerRequest,
        FetchIncomeStatementRequest,
        FetchBalanceSheetRequest,
        FetchCashFlowStatementRequest,
        FetchRatioRequest,
    ],
    Field(discriminator="request_type"),
]

_ADAPTER: TypeAdapter[AnyRequest] = TypeAdapter(AnyRequest)


def parse_request(payload: bytes | str | dict) -> Request:
    """Validate an incoming payload against the discriminated union.

    Raises `pydantic.ValidationError` on bad shapes so callers can treat
    invalid payloads as poison and route them to logs/DLQ.
    """
    if isinstance(payload, (bytes, str)):
        return _ADAPTER.validate_json(payload)
    return _ADAPTER.validate_python(payload)


__all__ = [
    "AnyRequest",
    "FetchBalanceSheetRequest",
    "FetchCashFlowStatementRequest",
    "FetchRatioRequest",
    "FetchIncomeStatementRequest",
    "FetchTickerRequest",
    "Request",
    "ValidationError",
    "parse_request",
]
