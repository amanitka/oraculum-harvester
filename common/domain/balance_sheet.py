"""Flat Pydantic model for SimFin balance sheets across industry templates."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

import pandas as pd
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    computed_field,
    field_validator,
    model_validator,
)

BalanceSheetTemplate = Literal["general", "banks", "insurance"]
StatementVariant = Literal["annual", "quarterly", "ttm"]


def _variant_from_fiscal_period(value: Any) -> StatementVariant:
    if isinstance(value, str):
        normalized = value.strip().upper()
        if normalized == "FY":
            return "annual"
        if normalized == "TTM":
            return "ttm"
        if normalized in {"Q1", "Q2", "Q3", "Q4"}:
            return "quarterly"
    return "annual"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class BalanceSheet(BaseModel):
    """Standardized balance sheet record for the Oraculum Harvester.

    Covers SimFin's three industry schemas (general, banks, insurance) in a
    single flat shape designed to back a single relational table. Core fields
    are shared by every template; template-specific fields are ``None`` when
    the row comes from a template that does not report them. The ``template``
    and ``variant`` discriminators tell downstream consumers which fields and
    periodicity to expect.
    """

    model_config = ConfigDict(populate_by_name=True)

    # Discriminator ----------------------------------------------------------
    template: BalanceSheetTemplate
    variant: StatementVariant

    # Core identifiers (shared by all templates) -----------------------------
    company_id: int = Field(alias="SimFinId")
    ticker: str = Field(alias="Ticker")
    market: str
    currency: str = Field(alias="Currency")
    fiscal_year: int = Field(alias="Fiscal Year")
    fiscal_period: str = Field(alias="Fiscal Period")
    report_date: date = Field(alias="Report Date")
    publish_date: date = Field(alias="Publish Date")
    restated_date: date | None = Field(alias="Restated Date", default=None)
    extracted_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    # Database-only field (populated from model_dump)
    statement_data: dict[str, Any] = Field(default_factory=dict)

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
        except TypeError, ValueError:
            pass
        return v

    @field_validator("report_date", "publish_date", "restated_date", mode="before")
    @classmethod
    def _parse_dates(cls, v: Any) -> Any:
        if isinstance(v, str):
            return date.fromisoformat(v)
        return v

    @model_validator(mode="before")
    @classmethod
    def _populate_variant(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        existing = data.get("variant")
        if isinstance(existing, str) and existing.strip():
            return data
        fiscal_period = data.get("Fiscal Period", data.get("fiscal_period"))
        payload = dict(data)
        payload["variant"] = _variant_from_fiscal_period(fiscal_period)
        return payload

    @computed_field  # type: ignore[prop-decorator]
    @property
    def id(self) -> str:
        """Generate the statement identifier for parquet and downstream storage.

        Example: ``111052-2023-FY-annual``.
        """
        return f"{self.company_id}-{self.fiscal_year}-{self.fiscal_period}-{self.variant}"
