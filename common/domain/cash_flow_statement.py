"""Flat Pydantic model for SimFin cash flow statements across industry templates."""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

CashFlowStatementTemplate = Literal["general", "banks", "insurance"]


class CashFlowStatement(BaseModel):
    """Standardized cash flow statement record for the Oraculum Harvester.

    Covers SimFin's three industry schemas (general, banks, insurance) in a
    single flat shape designed to back a single relational table. Core fields
    are shared by every template; template-specific fields are ``None`` when
    the row comes from a template that does not report them. The ``template``
    discriminator tells downstream consumers which fields to expect.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Discriminator ----------------------------------------------------------
    template: CashFlowStatementTemplate

    # Core identifiers (shared by all templates) -----------------------------
    ticker: str = Field(alias="Ticker")
    simfin_id: int = Field(alias="SimFinId")
    currency: str = Field(alias="Currency")
    fiscal_year: int = Field(alias="Fiscal Year")
    fiscal_period: str = Field(alias="Fiscal Period")
    report_date: date = Field(alias="Report Date")
    publish_date: date = Field(alias="Publish Date")
    restated_date: date | None = Field(alias="Restated Date", default=None)

    # Core share counts ------------------------------------------------------
    shares_basic: float | None = Field(alias="Shares (Basic)", default=None)
    shares_diluted: float | None = Field(alias="Shares (Diluted)", default=None)

    # Shared by all templates ------------------------------------------------
    net_income_starting_line: float | None = Field(
        alias="Net Income/Starting Line", default=None
    )
    depreciation_amortization: float | None = Field(
        alias="Depreciation & Amortization", default=None
    )
    non_cash_items: float | None = Field(alias="Non-Cash Items", default=None)
    net_cash_from_operating: float | None = Field(
        alias="Net Cash from Operating Activities", default=None
    )
    change_in_fixed_assets_intangibles: float | None = Field(
        alias="Change in Fixed Assets & Intangibles", default=None
    )
    net_cash_from_investing: float | None = Field(
        alias="Net Cash from Investing Activities", default=None
    )
    dividends_paid: float | None = Field(alias="Dividends Paid", default=None)
    cash_from_repayment_of_debt: float | None = Field(
        alias="Cash from (Repayment of) Debt", default=None
    )
    cash_from_repurchase_of_equity: float | None = Field(
        alias="Cash from (Repurchase of) Equity", default=None
    )
    net_cash_from_financing: float | None = Field(
        alias="Net Cash from Financing Activities", default=None
    )
    net_change_in_cash: float | None = Field(alias="Net Change in Cash", default=None)

    # Shared by general + banks (absent in insurance) ------------------------
    change_in_working_capital: float | None = Field(
        alias="Change in Working Capital", default=None
    )
    net_cash_from_acquisitions_divestitures: float | None = Field(
        alias="Net Cash from Acquisitions & Divestitures", default=None
    )

    # Shared by banks + insurance (absent in general) ------------------------
    effect_of_foreign_exchange_rates: float | None = Field(
        alias="Effect of Foreign Exchange Rates", default=None
    )

    # General template only --------------------------------------------------
    change_in_accounts_receivable: float | None = Field(
        alias="Change in Accounts Receivable", default=None
    )
    change_in_inventories: float | None = Field(
        alias="Change in Inventories", default=None
    )
    change_in_accounts_payable: float | None = Field(
        alias="Change in Accounts Payable", default=None
    )
    change_in_other: float | None = Field(alias="Change in Other", default=None)
    net_change_in_long_term_investment: float | None = Field(
        alias="Net Change in Long Term Investment", default=None
    )

    # Banks template only ----------------------------------------------------
    provision_for_loan_losses: float | None = Field(
        alias="Provision for Loan Losses", default=None
    )
    net_change_in_loans_interbank: float | None = Field(
        alias="Net Change in Loans & Interbank", default=None
    )

    # Insurance template only ------------------------------------------------
    net_change_in_investments: float | None = Field(
        alias="Net Change in Investments", default=None
    )

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_missing(cls, v: Any) -> Any:
        """Turn pandas NaN/NaT and empty strings into ``None`` for every field."""
        if v is None:
            return None
        if isinstance(v, str):
            return v if v.strip() else None
        try:
            if pd.isna(v):
                return None
        except (TypeError, ValueError):
            pass
        return v

    @field_validator("report_date", "publish_date", "restated_date", mode="before")
    @classmethod
    def _parse_dates(cls, v: Any) -> Any:
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v

    @computed_field  # type: ignore[prop-decorator]
    @property
    def composite_key(self) -> str:
        """Unique identifier for Kafka keys and the downstream ORM primary key.

        Example: ``AAPL-2023-FY-general``. Includes ``template`` so rows for
        the same ticker/period across schemas never collide.
        """
        return (
            f"{self.ticker}-{self.fiscal_year}-{self.fiscal_period}-{self.template}"
        )
