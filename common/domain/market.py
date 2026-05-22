from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


class Market(BaseModel):
    """Domain model representing a financial market from SimFin."""

    model_config = ConfigDict(populate_by_name=True)

    market_id: str = Field(..., alias="MarketId")
    market_name: str = Field(..., alias="Market Name")
    currency: Optional[str] = Field(None, alias="Currency")

    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("market_id", mode="before")
    @classmethod
    def coerce_identifier_to_string(cls, value: int | str | None) -> str:
        if value is None:
            raise ValueError("market_id cannot be None")
        return str(value)
