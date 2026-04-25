"""Flat Pydantic model for SimFin balance sheets across industry templates."""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

BalanceSheetTemplate = Literal["general", "banks", "insurance"]


class BalanceSheet(BaseModel):
    """Standardized balance sheet record for the Oraculum Harvester.

    Covers SimFin's three industry schemas (general, banks, insurance) in a
    single flat shape designed to back a single relational table. Core fields
    are shared by every template; template-specific fields are ``None`` when
    the row comes from a template that does not report them. The ``template``
    discriminator tells downstream consumers which fields to expect.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Discriminator ----------------------------------------------------------
    template: BalanceSheetTemplate

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

    # Shared by all templates ------------------------------------------------
    cash_and_equivalents: float | None = Field(
        alias="Cash, Cash Equivalents & Short Term Investments", default=None
    )
    accounts_notes_receivable: float | None = Field(
        alias="Accounts & Notes Receivable", default=None
    )
    total_assets: float | None = Field(alias="Total Assets", default=None)
    short_term_debt: float | None = Field(alias="Short Term Debt", default=None)
    long_term_debt: float | None = Field(alias="Long Term Debt", default=None)
    total_liabilities: float | None = Field(alias="Total Liabilities", default=None)
    share_capital_additional_paid_in: float | None = Field(
        alias="Share Capital & Additional Paid-In Capital", default=None
    )
    treasury_stock: float | None = Field(alias="Treasury Stock", default=None)
    retained_earnings: float | None = Field(alias="Retained Earnings", default=None)
    total_equity: float | None = Field(alias="Total Equity", default=None)
    total_liabilities_and_equity: float | None = Field(
        alias="Total Liabilities & Equity", default=None
    )

    # Shared by general + insurance (absent in banks) ------------------------
    property_plant_equipment_net: float | None = Field(
        alias="Property, Plant & Equipment, Net", default=None
    )

    # Shared by banks + insurance (absent in general) ------------------------
    preferred_equity: float | None = Field(alias="Preferred Equity", default=None)

    # General template only --------------------------------------------------
    inventories: float | None = Field(alias="Inventories", default=None)
    total_current_assets: float | None = Field(
        alias="Total Current Assets", default=None
    )
    long_term_investments_receivables: float | None = Field(
        alias="Long Term Investments & Receivables", default=None
    )
    other_long_term_assets: float | None = Field(
        alias="Other Long Term Assets", default=None
    )
    total_noncurrent_assets: float | None = Field(
        alias="Total Noncurrent Assets", default=None
    )
    payables_accruals: float | None = Field(alias="Payables & Accruals", default=None)
    total_current_liabilities: float | None = Field(
        alias="Total Current Liabilities", default=None
    )
    total_noncurrent_liabilities: float | None = Field(
        alias="Total Noncurrent Liabilities", default=None
    )

    # Banks template only ----------------------------------------------------
    interbank_assets: float | None = Field(alias="Interbank Assets", default=None)
    short_and_long_term_investments: float | None = Field(
        alias="Short & Long Term Investments", default=None
    )
    net_loans: float | None = Field(alias="Net Loans", default=None)
    net_fixed_assets: float | None = Field(alias="Net Fixed Assets", default=None)
    total_deposits: float | None = Field(alias="Total Deposits", default=None)

    # Insurance template only ------------------------------------------------
    total_investments: float | None = Field(alias="Total Investments", default=None)
    insurance_reserves: float | None = Field(alias="Insurance Reserves", default=None)
    policyholders_equity: float | None = Field(
        alias="Policyholders Equity", default=None
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
