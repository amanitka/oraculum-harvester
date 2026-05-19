"""Read-only repository for daily market signals."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.models.daily_market_signals import DailyMarketSignalDB

_DEFAULT_LIMIT = 500
_MAX_LIMIT = 5_000


class DailyMarketSignalsQuery(BaseModel):
    """Validated filters for querying daily market signals from the database view."""

    model_config = ConfigDict(frozen=True)

    ticker: str | None = None
    market: str | None = None
    from_date: date | None = None
    to_date: date | None = None
    only_month_end: bool = False
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

    @field_validator("market", mode="before")
    @classmethod
    def _normalize_market(cls, value: Any) -> Any:
        if isinstance(value, str):
            normalized = value.strip().lower()
            if not normalized:
                return None
            return normalized
        return value


class DailyMarketSignalsRepository:
    """Read access to market and fundamental point-in-time signal metrics."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch(self, query: DailyMarketSignalsQuery) -> list[DailyMarketSignalDB]:
        """Return market signal rows matching the provided filters."""
        statement = select(DailyMarketSignalDB)
        if query.ticker is not None:
            statement = statement.where(DailyMarketSignalDB.ticker == query.ticker)
        if query.market is not None:
            statement = statement.where(DailyMarketSignalDB.market == query.market)
        if query.from_date is not None:
            statement = statement.where(DailyMarketSignalDB.trade_date >= query.from_date)
        if query.to_date is not None:
            statement = statement.where(DailyMarketSignalDB.trade_date <= query.to_date)
        if query.only_month_end:
            statement = statement.where(DailyMarketSignalDB.flag_last_day_of_month == "Y")

        statement = statement.order_by(
            DailyMarketSignalDB.ticker.asc(),
            DailyMarketSignalDB.trade_date.desc(),
        )
        result = await self._session.exec(
            statement.limit(query.limit).offset(query.offset)
        )
        return list(result.all())
