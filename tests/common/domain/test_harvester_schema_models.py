"""Regression tests for harvester-facing schema models."""

from __future__ import annotations

from common.domain.balance_sheet import BalanceSheet
from common.domain.cash_flow_statement import CashFlowStatement
from common.domain.company import Company
from common.domain.income_statement import IncomeStatement
from common.domain.share_price import SharePrice


def test_company_maps_simfin_id_to_id() -> None:
    """Map SimFin identifiers to the company primary-key field."""
    company = Company.model_validate(
        {
            "SimFinId": 123,
            "Ticker": "AAPL",
            "market": "us",
            "Company Name": "Apple Inc.",
            "IndustryId": 10,
            "Currency": "USD",
        }
    )

    assert company.id == 123
    assert company.ticker == "AAPL"


def test_income_statement_id_uses_company_id_variant() -> None:
    """Generate statement ids from company id, fiscal period, and variant."""
    statement = IncomeStatement.model_validate(
        {
            "SimFinId": 321,
            "market": "us",
            "template": "general",
            "variant": "annual",
            "Currency": "USD",
            "Fiscal Year": 2024,
            "Fiscal Period": "FY",
            "Report Date": "2024-12-31",
            "Publish Date": "2025-02-14",
            "payload": {"Revenue": 1},
        }
    )

    assert statement.company_id == 321
    assert statement.id == "321-2024-FY-annual"


def test_balance_sheet_id_uses_company_id_variant() -> None:
    """Generate balance-sheet ids from company id, fiscal period, and variant."""
    statement = BalanceSheet.model_validate(
        {
            "SimFinId": 654,
            "market": "us",
            "template": "banks",
            "variant": "quarterly",
            "Currency": "USD",
            "Fiscal Year": 2024,
            "Fiscal Period": "Q1",
            "Report Date": "2024-03-31",
            "Publish Date": "2024-04-25",
            "payload": {"Assets": 1},
        }
    )

    assert statement.company_id == 654
    assert statement.id == "654-2024-Q1-quarterly"


def test_cash_flow_statement_id_uses_company_id_variant() -> None:
    """Generate cash-flow ids from company id, fiscal period, and variant."""
    statement = CashFlowStatement.model_validate(
        {
            "SimFinId": 987,
            "market": "us",
            "template": "insurance",
            "variant": "ttm",
            "Currency": "USD",
            "Fiscal Year": 2024,
            "Fiscal Period": "Q4",
            "Report Date": "2024-12-31",
            "Publish Date": "2025-02-20",
            "payload": {"Operating Cash Flow": 1},
        }
    )

    assert statement.company_id == 987
    assert statement.id == "987-2024-Q4-ttm"


def test_share_price_maps_simfin_id_to_company_id() -> None:
    """Map share price SimFin id to company_id output field."""
    share_price = SharePrice.model_validate(
        {
            "SimFinId": 111,
            "market": "us",
            "Currency": "USD",
            "Date": "2024-01-02",
            "Close": 10.5,
        }
    )

    assert share_price.company_id == 111
