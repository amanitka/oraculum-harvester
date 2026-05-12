"""Merge strategy for the derived dataset."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.loaders.base import ParquetMergeStrategy


class DerivedStrategy(ParquetMergeStrategy):
    """Handles bulk loading and upserting into the t_derived table."""

    async def merge(
        self, session: AsyncSession, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        """Load derived parquet records into staging and upsert into t_derived."""
        await self._create_staging_table(session, stg_table)
        await self._insert_records(session, stg_table, records)
        await self._upsert_records(session, stg_table)

    @staticmethod
    async def _create_staging_table(session: AsyncSession, stg_table: str) -> None:
        await session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_derived INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )
        await session.exec(
            text(f"""
            ALTER TABLE {stg_table} ALTER COLUMN created_at DROP NOT NULL, ALTER COLUMN updated_at DROP NOT NULL;
        """)
        )

    @staticmethod
    async def _insert_records(
        session: AsyncSession, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        await session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                composite_key, template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                ebitda, free_cash_flow, ncav, net_net_working_capital, shares_stabilized, return_on_equity, net_margin, revenue, net_income
            )
            VALUES (
                :composite_key, :template, :variant, :ticker, :simfin_id, :currency, :fiscal_year, :fiscal_period, :report_date, :publish_date, :restated_date, :extracted_at,
                :ebitda, :free_cash_flow, :ncav, :net_net_working_capital, :shares_stabilized, :return_on_equity, :net_margin, :revenue, :net_income
            )
        """),
            params=records,
        )

    @staticmethod
    async def _upsert_records(session: AsyncSession, stg_table: str) -> None:
        await session.exec(
            text(f"""
            INSERT INTO t_derived (
                composite_key, template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                ebitda, free_cash_flow, ncav, net_net_working_capital, shares_stabilized, return_on_equity, net_margin, revenue, net_income,
                created_at, updated_at
            )
            SELECT composite_key, template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                   ebitda, free_cash_flow, ncav, net_net_working_capital, shares_stabilized, return_on_equity, net_margin, revenue, net_income,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM {stg_table}
            ON CONFLICT (composite_key) DO UPDATE SET
                simfin_id = EXCLUDED.simfin_id,
                currency = EXCLUDED.currency,
                report_date = EXCLUDED.report_date,
                publish_date = EXCLUDED.publish_date,
                restated_date = EXCLUDED.restated_date,
                extracted_at = EXCLUDED.extracted_at,
                ebitda = EXCLUDED.ebitda,
                free_cash_flow = EXCLUDED.free_cash_flow,
                ncav = EXCLUDED.ncav,
                net_net_working_capital = EXCLUDED.net_net_working_capital,
                shares_stabilized = EXCLUDED.shares_stabilized,
                return_on_equity = EXCLUDED.return_on_equity,
                net_margin = EXCLUDED.net_margin,
                revenue = EXCLUDED.revenue,
                net_income = EXCLUDED.net_income,
                updated_at = CURRENT_TIMESTAMP
        """)
        )
