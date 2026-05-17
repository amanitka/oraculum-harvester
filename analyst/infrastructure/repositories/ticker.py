"""Async persistence gateway for `TickerDB`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.models.ticker import TickerDB
from common.domain.ticker import Ticker


class TickerRepository:
    """Read/write access to the `ticker` table.

    The repository owns the SQL dialect concerns and keeps the rest of
    the analyst service ignorant of SQLModel specifics. Each instance is
    bound to a single `AsyncSession` so callers control the transaction
    boundary.
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, ticker: Ticker) -> TickerDB:
        """Insert or fully refresh the row for `(ticker, market)`.

        Upstream is treated as the source of truth: every field from the
        domain model overwrites the corresponding column. `created_at`
        is preserved on update; `updated_at` is refreshed.
        """
        existing = await self.get_by_ticker(ticker.ticker, ticker.market)
        payload = ticker.model_dump()
        if existing is None:
            row = TickerDB(**payload)
            self._session.add(row)
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            row = existing
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def get_by_ticker(self, ticker: str, market: str = "us") -> Optional[TickerDB]:
        stmt = select(TickerDB).where(
            TickerDB.ticker == ticker,
            TickerDB.market == market,
        )
        result = await self._session.exec(stmt)
        return result.first()

    async def list_all_tickers(self) -> list[TickerDB]:
        """Fetch all tickers from the database."""
        statement = select(TickerDB).order_by(TickerDB.ticker.asc())
        result = await self._session.exec(statement)
        return result.all()
