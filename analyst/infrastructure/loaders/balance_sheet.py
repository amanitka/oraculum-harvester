"""Merge strategy for the balance_sheet dataset."""

from __future__ import annotations

from typing import Any

from sqlalchemy import bindparam, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.loaders.base import ParquetMergeStrategy


class BalanceSheetStrategy(ParquetMergeStrategy):
    """Handles bulk loading and upserting into the t_balance_sheet table."""

    async def merge(
        self, session: AsyncSession, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        await session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_balance_sheet INCLUDING DEFAULTS) ON COMMIT DROP;
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
                composite_key, template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                payload
            )
            VALUES (
                :composite_key, :template, :variant, :ticker, :simfin_id, :currency, :fiscal_year, :fiscal_period, :report_date, :publish_date, :restated_date, :extracted_at,
                :payload
            )
        """).bindparams(bindparam("payload", type_=JSONB())),
            params=records,
        )

        await session.exec(
            text(f"""
            INSERT INTO t_balance_sheet (
                composite_key, template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                payload, created_at, updated_at
            )
            SELECT composite_key, template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at, payload,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM {stg_table}
            ON CONFLICT (composite_key) DO UPDATE SET
                simfin_id = EXCLUDED.simfin_id,
                currency = EXCLUDED.currency,
                report_date = EXCLUDED.report_date,
                publish_date = EXCLUDED.publish_date,
                restated_date = EXCLUDED.restated_date,
                extracted_at = EXCLUDED.extracted_at,
                payload = EXCLUDED.payload,
                updated_at = CURRENT_TIMESTAMP
        """)
        )
