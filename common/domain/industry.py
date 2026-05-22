from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Industry(BaseModel):
    """Domain model representing an industry and sector from SimFin."""

    model_config = ConfigDict(populate_by_name=True)

    industry_id: str = Field(..., alias="IndustryId")
    sector_name: str = Field(..., alias="Sector")
    industry_name: str = Field(..., alias="Industry")

    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("industry_id", mode="before")
    @classmethod
    def coerce_identifier_to_string(cls, value: int | str | None) -> str:
        if value is None:
            raise ValueError("industry_id cannot be None")
        return str(value)
