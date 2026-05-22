"""Read-only repository for on-demand derived metrics."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.models.derived_metrics import DerivedMetricsDB

StatementTemplate = Literal["general", "banks", "insurance"]
StatementVariant = Literal["annual", "quarterly", "ttm"]

_DEFAULT_LIMIT = 500
_MAX_LIMIT = 5_000


class DerivedMetricsQuery(BaseModel):
    """Validated filters for querying derived metrics from the database view."""

    model_config = ConfigDict(frozen=True)

    ticker: str | None = None
    template: StatementTemplate | None = "general"
    variant: StatementVariant | None = None
    limit: int = Field(default=_DEFAULT_LIMIT, ge=1, le=_MAX_LIMIT)
    offset: int = Field(default=0, ge=0)

    @field_validator("ticker")
    @classmethod
    def _normalize_ticker(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().upper()
        if not normalized:
            return None
        return normalized

    @field_validator("template", "variant", mode="before")
    @classmethod
    def _normalize_filter(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip().lower()
        return value


class DerivedMetricsRepository:
    """Read access to derived metrics calculated from persisted statements."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: DerivedMetricsQuery) -> list[DerivedMetricsDB]:
        """Return derived metrics matching the provided filters."""
        statement = select(DerivedMetricsDB)
        if query.ticker is not None:
            statement = statement.where(DerivedMetricsDB.ticker == query.ticker)
        if query.template is not None:
            statement = statement.where(DerivedMetricsDB.template == query.template)
        if query.variant is not None:
            statement = statement.where(DerivedMetricsDB.variant == query.variant)
        statement = statement.order_by(
            DerivedMetricsDB.ticker.asc(),
            DerivedMetricsDB.fiscal_year.desc(),
            DerivedMetricsDB.fiscal_period.desc(),
            DerivedMetricsDB.report_date.desc(),
        )
        result = await self._session.exec(statement.limit(query.limit).offset(query.offset))
        return list(result.all())
