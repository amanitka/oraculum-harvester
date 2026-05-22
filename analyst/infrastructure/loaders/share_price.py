"""Merge strategy for the share_price dataset."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.loaders.base import ParquetMergeStrategy


class SharePriceStrategy(ParquetMergeStrategy):
    """Handles bulk loading and upserting into the t_share_price table."""

    async def merge(self, session: AsyncSession, stg_table: str, records: list[dict[str, Any]]) -> None:
        await session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_share_price INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )
        await session.exec(
            text(f"""
            ALTER TABLE {stg_table} ALTER COLUMN created_at DROP NOT NULL, ALTER COLUMN updated_at DROP NOT NULL;
        """)
        )

        await session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                ticker, sim_fin_id, currency, market, trade_date, open, high, low, close,
                adj_close, volume, shares_outstanding, dividend, extracted_at
            )
            VALUES (
                :ticker, :sim_fin_id, :currency, :market, :trade_date, :open, :high, :low, :close,
                :adj_close, :volume, :shares_outstanding, :dividend, :extracted_at
            )
        """),
            params=records,
        )

        await session.exec(
            text(f"""
            INSERT INTO t_share_price (
                ticker, sim_fin_id, currency, market, trade_date, open, high, low, close,
                adj_close, volume, shares_outstanding, dividend, extracted_at,
                created_at, updated_at
            )
            SELECT ticker, sim_fin_id, currency, market, trade_date, open, high, low, close,
                   adj_close, volume, shares_outstanding, dividend, extracted_at,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM {stg_table}
            ON CONFLICT (ticker, market, trade_date) DO UPDATE SET
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
                extracted_at = EXCLUDED.extracted_at,
                updated_at = CURRENT_TIMESTAMP
        """)
        )
