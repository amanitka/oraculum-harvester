"""Flat Pydantic model for SimFin income statements across industry templates."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

IncomeStatementTemplate = Literal["general", "banks", "insurance"]


class IncomeStatement(BaseModel):
    """Standardized income statement record for the Oraculum Harvester.

    Covers SimFin's three industry schemas (general, banks, insurance) in a
    single flat shape designed to back a single relational table. Core fields
    are shared by every template; template-specific fields are ``None`` when
    the row comes from a template that does not report them. The ``template``
    discriminator tells downstream consumers which fields to expect.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Discriminator ----------------------------------------------------------
    template: IncomeStatementTemplate

    # Core identifiers (shared by all templates) -----------------------------
    ticker: str = Field(alias="Ticker")
    simfin_id: int = Field(alias="SimFinId")
    currency: str = Field(alias="Currency")
    fiscal_year: int = Field(alias="Fiscal Year")
    fiscal_period: str = Field(alias="Fiscal Period")
    report_date: date = Field(alias="Report Date")
    publish_date: date = Field(alias="Publish Date")
    restated_date: date | None = Field(alias="Restated Date", default=None)
    extracted_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    # Core share counts ------------------------------------------------------
    shares_basic: float | None = Field(alias="Shares (Basic)", default=None)
    shares_diluted: float | None = Field(alias="Shares (Diluted)", default=None)

    # Core revenue & bottom line --------------------------------------------
    revenue: float | None = Field(alias="Revenue", default=None)
    operating_income: float | None = Field(alias="Operating Income (Loss)", default=None)
    pretax_income: float | None = Field(alias="Pretax Income (Loss)", default=None)
    income_tax_benefit_net: float | None = Field(
        alias="Income Tax (Expense) Benefit, Net", default=None
    )
    income_continuing_ops: float | None = Field(
        alias="Income (Loss) from Continuing Operations", default=None
    )
    net_extraordinary_gains: float | None = Field(
        alias="Net Extraordinary Gains (Losses)", default=None
    )
    net_income: float | None = Field(alias="Net Income", default=None)
    net_income_common: float | None = Field(alias="Net Income (Common)", default=None)

    # Shared by general + banks (absent in insurance) ------------------------
    non_operating_income: float | None = Field(
        alias="Non-Operating Income (Loss)", default=None
    )

    # General template only --------------------------------------------------
    cost_of_revenue: float | None = Field(alias="Cost of Revenue", default=None)
    gross_profit: float | None = Field(alias="Gross Profit", default=None)
    operating_expenses: float | None = Field(alias="Operating Expenses", default=None)
    selling_general_admin: float | None = Field(
        alias="Selling, General & Administrative", default=None
    )
    research_development: float | None = Field(
        alias="Research & Development", default=None
    )
    depreciation_amortization: float | None = Field(
        alias="Depreciation & Amortization", default=None
    )
    interest_expense_net: float | None = Field(
        alias="Interest Expense, Net", default=None
    )
    pretax_income_adj: float | None = Field(
        alias="Pretax Income (Loss), Adj.", default=None
    )
    abnormal_gains_losses: float | None = Field(
        alias="Abnormal Gains (Losses)", default=None
    )

    # Banks template only ----------------------------------------------------
    provision_for_loan_losses: float | None = Field(
        alias="Provision for Loan Losses", default=None
    )
    net_revenue_after_provisions: float | None = Field(
        alias="Net Revenue after Provisions", default=None
    )
    total_non_interest_expense: float | None = Field(
        alias="Total Non-Interest Expense", default=None
    )

    # Insurance template only ------------------------------------------------
    total_claims_losses: float | None = Field(
        alias="Total Claims & Losses", default=None
    )
    income_from_affiliates_net: float | None = Field(
        alias="Income (Loss) from Affiliates, Net of Taxes", default=None
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
