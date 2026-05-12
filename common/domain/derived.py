"""Derived financial metric domain model."""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any, Literal

import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator

DerivedTemplate = Literal["general"]
StatementVariant = Literal["annual", "quarterly", "ttm"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Derived(BaseModel):
    """Calculated financial metrics for one SimFin statement period."""

    model_config = ConfigDict(populate_by_name=True)

    template: DerivedTemplate
    variant: StatementVariant
    ticker: str
    simfin_id: int
    currency: str
    fiscal_year: int
    fiscal_period: str
    report_date: date
    publish_date: date
    restated_date: date | None = None
    extracted_at: datetime = Field(default_factory=_utcnow)

    ebitda: float | None = None
    free_cash_flow: float | None = None
    ncav: float | None = None
    net_net_working_capital: float | None = None
    shares_stabilized: float | None = None
    return_on_equity: float | None = None
    net_margin: float | None = None
    revenue: float | None = None
    net_income: float | None = None

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
        """Coerce string and pandas timestamps to ``date``."""
        if isinstance(v, str):
            return date.fromisoformat(v)
        if hasattr(v, "date") and callable(v.date):
            return v.date()
        return v

    @computed_field
    @property
    def composite_key(self) -> str:
        """Return the unique key used by Kafka and the downstream table."""
        return (
            f"{self.ticker}-{self.fiscal_year}-{self.fiscal_period}-{self.template}-"
            f"{self.variant}"
        )
