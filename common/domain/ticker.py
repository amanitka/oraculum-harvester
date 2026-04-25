from datetime import datetime, timezone

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import Optional
import math


class Ticker(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    # Standard names used throughout your Oraculum app
    symbol: str = Field(..., alias="Ticker")
    provider_id: Optional[str] = Field(None, alias="SimFinId")
    provider_name: Optional[str] = None
    company_name: str = Field(..., alias="Company Name")

    # Financial Metadata
    industry_id: Optional[str] = Field(None, alias="IndustryId")
    industry_name: Optional[str] = None
    sector_name: Optional[str] = None
    isin: Optional[str] = Field(None, alias="ISIN")
    description: Optional[str] = Field(None, alias="Business Summary")
    employee_count: Optional[int] = Field(None, alias="Number Employees")

    # Location/Identity
    market: str = Field("us", alias="Market")
    currency: str = Field("USD", alias="Main Currency")
    cik: Optional[str] = Field(None, alias="CIK")

    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("provider_id", "industry_id", "cik", mode="before")
    @classmethod
    def coerce_identifier_to_string(
        cls, value: int | float | str | None
    ) -> str | None:
        if value is None:
            return None
        if isinstance(value, float):
            if math.isnan(value):
                return None
            if value.is_integer():
                return str(int(value))
            return str(value)
        if isinstance(value, int):
            return str(value)
        return value

    @field_validator('*', mode='before')
    @classmethod
    def handle_nan(cls, v: float | str | None) -> float | str | None:
        if isinstance(v, float) and math.isnan(v):
            return None
        return v

