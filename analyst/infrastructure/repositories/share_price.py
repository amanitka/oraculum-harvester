"""Async persistence gateway for `SharePriceDB`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.models.share_price import SharePriceDB
from common.domain.share_price import SharePrice


class SharePriceRepository:
    """Read/write access to the `t_share_price` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, share_price: SharePrice) -> SharePriceDB:
        """Insert or fully refresh the row keyed by `(ticker, market, trade_date)`."""
        existing = await self._find(
            share_price.ticker, share_price.market, share_price.trade_date
        )
        payload = share_price.model_dump()
        
        # trade_date is a datetime.date object. Pydantic handles this gracefully,
        # but just to be safe it's mapped directly into the DB model.
        if existing is None:
            row = SharePriceDB(**payload)
            self._session.add(row)
        else:
            for key, value in payload.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            row = existing
            
        await self._session.commit()
        
        # When using Postgres range partitions with composite primary keys, 
        # refresh might sometimes struggle depending on the dialect config,
        # but SQLModel handles it fine if primary keys are explicitly mapped.
        await self._session.refresh(row)
        return row

    async def _find(
        self, ticker: str, market: str, trade_date: datetime.date
    ) -> Optional[SharePriceDB]:
        stmt = select(SharePriceDB).where(
            SharePriceDB.ticker == ticker,
            SharePriceDB.market == market,
            SharePriceDB.trade_date == trade_date,
        )
        result = await self._session.exec(stmt)
        return result.first()
