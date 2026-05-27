from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

IndustryStatementTemplate = Literal["general", "banks", "insurance"]


class Industry(BaseModel):
    """Domain model representing an industry and sector from SimFin."""

    model_config = ConfigDict(populate_by_name=True)

    industry_id: str = Field(..., alias="industryId")
    sector_name: str = Field(..., alias="sectorName")
    industry_name: str = Field(..., alias="industryName")
    statement_template: IndustryStatementTemplate = Field(default="general", alias="statementTemplate")

    extracted_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), alias="extractedAt")

    @field_validator("industry_id", mode="before")
    @classmethod
    def coerce_identifier_to_string(cls, value: int | str | None) -> str:
        if value is None:
            raise ValueError("industryId cannot be None")
        return str(value)

    @field_validator("statement_template", mode="before")
    @classmethod
    def normalize_statement_template(cls, value: str | None) -> IndustryStatementTemplate:
        if value is None:
            return "general"
        normalized_value = value.strip().lower()
        if normalized_value == "banks":
            return "banks"
        if normalized_value == "insurance":
            return "insurance"
        return "general"
