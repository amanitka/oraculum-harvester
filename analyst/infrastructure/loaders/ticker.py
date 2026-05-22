"""Merge strategy for the ticker dataset."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.loaders.base import ParquetMergeStrategy

logger = logging.getLogger(__name__)


class TickerStrategy(ParquetMergeStrategy):
    """Handles bulk loading and upserting into the t_ticker table."""

    async def merge(self, session: AsyncSession, stg_table: str, records: list[dict[str, Any]]) -> None:
        """
        Merge records from a Parquet file into the target table.

        This implementation first loads data into a temporary staging table, then
        uses a single `INSERT ... ON CONFLICT` statement to perform an "upsert"
        into the final destination table (`t_ticker`).

        This approach is significantly more performant for large datasets than
        iterating and updating row-by-row.

        Args:
            session: The asynchronous database session.
            stg_table: The name of the temporary staging table.
            records: A list of dictionaries representing the rows to be inserted.
        """
        # Create a temporary table to stage the incoming data.
        # This table is a clone of the target table but without constraints
        # and is dropped at the end of the transaction.
        await session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_ticker INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )

        # The temp table inherits NOT NULL constraints, which we don't want to
        # enforce for the initial bulk insert. We'll let the final merge
        # into the destination table handle constraint validation.
        await session.exec(
            text(f"""
            ALTER TABLE {stg_table} ALTER COLUMN created_at DROP NOT NULL, ALTER COLUMN updated_at DROP NOT NULL;
        """)
        )

        # Bulk insert all records from the Parquet file into the staging table.
        # SQLAlchemy's `exec` with a list of dicts is highly optimized for this.
        await session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                ticker, provider_id, provider_name, company_name, industry_id, industry_name,
                sector_name, isin, description, employee_count, market, currency, cik, extracted_at
            )
            VALUES (
                :ticker, :provider_id, :provider_name, :company_name, :industry_id, :industry_name,
                :sector_name, :isin, :description, :employee_count, :market, :currency, :cik, :extracted_at
            )
        """),
            params=records,
        )

        # Upsert from the staging table into the final destination table.
        # `ON CONFLICT` is a PostgreSQL-specific feature that provides a clean
        # and efficient way to handle conflicts on a unique constraint.
        await session.exec(
            text(f"""
            INSERT INTO t_ticker (
                ticker, provider_id, provider_name, company_name, industry_id, industry_name,
                sector_name, isin, description, employee_count, market, currency, cik, extracted_at,
                created_at, updated_at
            )
            SELECT ticker, provider_id, provider_name, company_name, industry_id, industry_name,
                   sector_name, isin, description, employee_count, market, currency, cik, extracted_at,
                   CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            FROM {stg_table}
            ON CONFLICT (ticker, market) DO UPDATE SET
                provider_id = EXCLUDED.provider_id,
                provider_name = EXCLUDED.provider_name,
                company_name = EXCLUDED.company_name,
                industry_id = EXCLUDED.industry_id,
                industry_name = EXCLUDED.industry_name,
                sector_name = EXCLUDED.sector_name,
                isin = EXCLUDED.isin,
                description = EXCLUDED.description,
                employee_count = EXCLUDED.employee_count,
                currency = EXCLUDED.currency,
                cik = EXCLUDED.cik,
                extracted_at = EXCLUDED.extracted_at,
                updated_at = CURRENT_TIMESTAMP
        """)
        )
