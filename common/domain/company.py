"""Company master-data domain model."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Company(BaseModel):
    """Represent one normalized company row extracted from SimFin."""

    model_config = ConfigDict(populate_by_name=True)

    id: int = Field(alias="SimFinId")
    ticker: str = Field(alias="Ticker")
    market: str
    company_name: str = Field(alias="Company Name")
    industry_id: int | None = Field(default=None, alias="IndustryId")
    industry_name: str | None = None
    sector_name: str | None = None
    isin: str | None = Field(default=None, alias="ISIN")
    description: str | None = Field(default=None, alias="Business Summary")
    employee_count: int | None = Field(default=None, alias="Number Employees")
    currency: str = Field(alias="Currency")
    cik: str | None = Field(default=None, alias="CIK")
    extracted_at: datetime = Field(default_factory=_utcnow)
    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)

    @field_validator("*", mode="before")
    @classmethod
    def _coerce_missing(cls, value: Any) -> Any:
        """Normalize NaN and blank strings to ``None``."""
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        if isinstance(value, str):
            stripped = value.strip()
            return stripped if stripped else None
        return value

    @field_validator("id", "industry_id", "employee_count", mode="before")
    @classmethod
    def _coerce_int_fields(cls, value: Any) -> Any:
        """Convert numeric identifier and count fields to ``int``."""
        if value is None:
            return None
        if isinstance(value, int):
            return value
        if isinstance(value, float):
            if math.isnan(value):
                return None
            return int(value)
        if isinstance(value, str):
            return int(float(value))
        return value

    @field_validator("cik", mode="before")
    @classmethod
    def _coerce_cik(cls, value: Any) -> str | None:
        """Coerce CIK values to canonical string representation."""
        if value is None:
            return None
        if isinstance(value, int):
            return str(value)
        if isinstance(value, float):
            if math.isnan(value):
                return None
            if value.is_integer():
                return str(int(value))
            return str(value)
        return str(value)
