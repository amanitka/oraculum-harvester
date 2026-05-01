"""Build validated harvester refresh requests from UI input."""

from __future__ import annotations

from datetime import date
from typing import Literal, TypeAlias, cast

from common.requests.balance_sheet import FetchBalanceSheetRequest
from common.requests.cash_flow_statement import FetchCashFlowStatementRequest
from common.requests.income_statement import FetchIncomeStatementRequest
from common.requests.share_price import FetchSharePriceRequest
from common.requests.ticker import FetchTickerRequest

StatementVariant: TypeAlias = Literal["annual", "quarterly", "ttm"]
StatementTemplate: TypeAlias = Literal["general", "banks", "insurance"]

STATEMENT_VARIANTS: tuple[StatementVariant, ...] = ("annual", "quarterly", "ttm")
STATEMENT_TEMPLATES: tuple[StatementTemplate, ...] = ("general", "banks", "insurance")


def build_ticker_request(market: str) -> FetchTickerRequest:
    """Build a ticker refresh request."""
    return FetchTickerRequest(market=_normalize_market(market))


def build_share_price_request(
    market: str,
    variant: str,
    from_date: date | None,
    safety_window_days: int,
) -> FetchSharePriceRequest:
    """Build a share-price refresh request."""
    validated_window = _validate_safety_window_days(safety_window_days)
    return FetchSharePriceRequest(
        market=_normalize_market(market),
        variant=_normalize_variant(variant),
        from_date=from_date,
        safety_window_days=validated_window,
    )


def build_income_statement_request(
    market: str,
    variant: str,
    templates: list[str],
) -> FetchIncomeStatementRequest:
    """Build an income-statement refresh request."""
    return FetchIncomeStatementRequest(
        market=_normalize_market(market),
        variant=_validate_variant(variant),
        templates=_validate_templates(templates, "income statement"),
    )


def build_balance_sheet_request(
    market: str,
    variant: str,
    templates: list[str],
) -> FetchBalanceSheetRequest:
    """Build a balance-sheet refresh request."""
    return FetchBalanceSheetRequest(
        market=_normalize_market(market),
        variant=_validate_variant(variant),
        templates=_validate_templates(templates, "balance sheet"),
    )


def build_cash_flow_statement_request(
    market: str,
    variant: str,
    templates: list[str],
) -> FetchCashFlowStatementRequest:
    """Build a cash-flow-statement refresh request."""
    return FetchCashFlowStatementRequest(
        market=_normalize_market(market),
        variant=_validate_variant(variant),
        templates=_validate_templates(templates, "cash flow statement"),
    )


def _normalize_market(market: str) -> str:
    normalized = market.strip().lower()
    if not normalized:
        raise ValueError("Market is required.")
    return normalized


def _validate_variant(variant: str) -> StatementVariant:
    normalized = variant.strip().lower()
    if normalized not in STATEMENT_VARIANTS:
        raise ValueError("Variant must be annual, quarterly, or ttm.")
    return cast(StatementVariant, normalized)


def _normalize_variant(variant: str) -> str:
    normalized = variant.strip().lower()
    if not normalized:
        raise ValueError("Variant is required.")
    return normalized


def _validate_templates(
    templates: list[str],
    request_label: str,
) -> list[StatementTemplate]:
    if not templates:
        raise ValueError(f"Select at least one template for {request_label} refresh.")

    normalized_templates = [template.strip().lower() for template in templates]
    invalid_templates = [
        template for template in normalized_templates if template not in STATEMENT_TEMPLATES
    ]
    if invalid_templates:
        raise ValueError(
            "Unsupported template values: " + ", ".join(sorted(set(invalid_templates)))
        )
    return [cast(StatementTemplate, template) for template in normalized_templates]


def _validate_safety_window_days(safety_window_days: int) -> int:
    if safety_window_days < 0:
        raise ValueError("Safety window days must be zero or higher.")
    return safety_window_days
