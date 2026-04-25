"""Bulk-upsert repository for ``t_share_price``."""

from __future__ import annotations

import logging

from sqlalchemy import text, TextClause
from sqlmodel.ext.asyncio.session import AsyncSession

from common.domain.share_price import SharePrice, SharePriceBatch

logger = logging.getLogger(__name__)

_UPSERT_SQL: TextClause = text(
    """
    INSERT INTO t_share_price (ticker, sim_fin_id, currency, market, trade_date,
                               open, high, low, close, adj_close,
                               volume, shares_outstanding, dividend, extracted_at)
    VALUES (:ticker, :sim_fin_id, :currency, :market, :trade_date,
            :open, :high, :low, :close, :adj_close,
            :volume, :shares_outstanding, :dividend, :extracted_at) ON CONFLICT (ticker, market, trade_date) DO
    UPDATE SET
        sim_fin_id = EXCLUDED.sim_fin_id,
        currency = EXCLUDED.currency,
        open = EXCLUDED.open,
        high = EXCLUDED.high,
        low = EXCLUDED.low,
        close = EXCLUDED.close,
        adj_close = EXCLUDED.adj_close,
        volume = EXCLUDED.volume,
        shares_outstanding = EXCLUDED.shares_outstanding,
        dividend = EXCLUDED.dividend,
        extracted_at = EXCLUDED.extracted_at
    """
)


def _row_to_params(row: SharePrice) -> dict:
    """Convert a ``SharePrice`` to a parameter dict for the upsert statement."""
    return {
        "ticker": row.ticker,
        "sim_fin_id": row.sim_fin_id,
        "currency": row.currency,
        "market": row.market,
        "trade_date": row.trade_date,
        "open": row.open,
        "high": row.high,
        "low": row.low,
        "close": row.close,
        "adj_close": row.adj_close,
        "volume": row.volume,
        "shares_outstanding": row.shares_outstanding,
        "dividend": row.dividend,
        "extracted_at": row.extracted_at,
    }


class SharePriceRepository:
    """Persistence gateway for ``t_share_price`` using bulk upserts."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def bulk_upsert(self, batch: SharePriceBatch) -> int:
        """Upsert all rows from ``batch``. Returns the number of rows processed."""
        if not batch.rows:
            return 0
        params = [_row_to_params(row) for row in batch.rows]
        await self._session.exec(_UPSERT_SQL, params)
        return len(params)
