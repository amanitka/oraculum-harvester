"""Monthly and yearly partition manager.

Creates any missing ``RANGE`` partitions from the historical data start date
up to ``months_ahead`` or ``years_ahead`` into the future. Idempotent: partitions that
already exist are skipped without error.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

_SHARE_PRICE_TABLE = "t_share_price"
_SHARE_PRICE_HISTORICAL_START = date(1990, 1, 1)

_NEWS_TABLE = "t_news"
_NEWS_TICKER_TABLE = "t_news_ticker"
# We retain 2 years of news data, so start date is typically close to today.
# We'll use a conservative start of 2020.
_NEWS_HISTORICAL_START = date(2020, 1, 1)


def _first_of_month(d: date) -> date:
    """Return the first day of ``d``'s month."""
    return date(d.year, d.month, 1)


def _next_month(d: date) -> date:
    """Return the first day of the month immediately after ``d``."""
    if d.month == 12:
        return date(d.year + 1, 1, 1)
    return date(d.year, d.month + 1, 1)


def _add_months(d: date, n: int) -> date:
    """Return ``d`` advanced by ``n`` calendar months, snapped to first of month."""
    month_total = d.month - 1 + n
    return date(d.year + month_total // 12, month_total % 12 + 1, 1)


def _first_of_year(d: date) -> date:
    """Return the first day of ``d``'s year."""
    return date(d.year, 1, 1)


def _next_year(d: date) -> date:
    """Return the first day of the year immediately after ``d``."""
    return date(d.year + 1, 1, 1)


class PartitionManager:
    """Ensures appropriate ``RANGE`` partitions exist."""

    @classmethod
    async def ensure_share_price_partitions(cls, session: AsyncSession, months_ahead: int = 9) -> None:
        """Create any missing monthly partitions.

        Covers ``_SHARE_PRICE_HISTORICAL_START`` through the current month plus
        ``months_ahead`` additional months (inclusive).
        """
        today_month = _first_of_month(date.today())
        end = _add_months(today_month, months_ahead + 1)

        existing = await cls._existing_partition_names(session, _SHARE_PRICE_TABLE)

        current = _first_of_month(_SHARE_PRICE_HISTORICAL_START)
        created = 0
        while current < end:
            name = f"{_SHARE_PRICE_TABLE}_{current.year:04d}_{current.month:02d}"
            if name not in existing:
                await cls._create_monthly_partition(session, _SHARE_PRICE_TABLE, name, current)
                created += 1
            current = _next_month(current)

        total_months = (
            (end.year - _SHARE_PRICE_HISTORICAL_START.year) * 12 + end.month - _SHARE_PRICE_HISTORICAL_START.month
        )
        logger.info(
            "Share price partition check complete: created=%d total_range_months=%d",
            created,
            total_months,
        )

    @classmethod
    async def ensure_news_partitions(cls, session: AsyncSession, years_ahead: int = 1) -> None:
        """Create any missing yearly partitions for news tables.

        Covers ``_NEWS_HISTORICAL_START`` through the current year plus
        ``years_ahead`` additional years (inclusive).
        Ensures identical partitions for both t_news and t_news_ticker.
        """
        today_year = _first_of_year(date.today())
        end = date(today_year.year + years_ahead + 1, 1, 1)

        existing_news = await cls._existing_partition_names(session, _NEWS_TABLE)
        existing_ticker = await cls._existing_partition_names(session, _NEWS_TICKER_TABLE)

        current = _first_of_year(_NEWS_HISTORICAL_START)
        created_news = 0
        created_ticker = 0

        while current < end:
            news_name = f"{_NEWS_TABLE}_{current.year:04d}"
            if news_name not in existing_news:
                await cls._create_yearly_partition(session, _NEWS_TABLE, news_name, current)
                created_news += 1

            ticker_name = f"{_NEWS_TICKER_TABLE}_{current.year:04d}"
            if ticker_name not in existing_ticker:
                await cls._create_yearly_partition(session, _NEWS_TICKER_TABLE, ticker_name, current)
                created_ticker += 1

            current = _next_year(current)

        total_years = end.year - _NEWS_HISTORICAL_START.year
        logger.info(
            "News partition check complete: news_created=%d ticker_created=%d total_range_years=%d",
            created_news,
            created_ticker,
            total_years,
        )

    @staticmethod
    async def _existing_partition_names(session: AsyncSession, base_table: str) -> set[str]:
        """Return names of existing partitions for a given base table."""
        result = await session.execute(
            text(f"SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE '{base_table}_%'")
        )
        return {row[0] for row in result}

    @staticmethod
    async def _create_monthly_partition(session: AsyncSession, base_table: str, name: str, month_start: date) -> None:
        """Issue a ``CREATE TABLE IF NOT EXISTS ... PARTITION OF`` statement for a month."""
        month_end = _next_month(month_start)
        await session.exec(
            text(
                f"CREATE TABLE IF NOT EXISTS {name}"
                f" PARTITION OF {base_table}"
                f" FOR VALUES FROM ('{month_start.isoformat()}')"
                f" TO ('{month_end.isoformat()}')"
            )
        )
        logger.debug("Created monthly partition %s", name)

    @staticmethod
    async def _create_yearly_partition(session: AsyncSession, base_table: str, name: str, year_start: date) -> None:
        """Issue a ``CREATE TABLE IF NOT EXISTS ... PARTITION OF`` statement for a year."""
        year_end = _next_year(year_start)
        await session.exec(
            text(
                f"CREATE TABLE IF NOT EXISTS {name}"
                f" PARTITION OF {base_table}"
                f" FOR VALUES FROM ('{year_start.isoformat()}')"
                f" TO ('{year_end.isoformat()}')"
            )
        )
        logger.debug("Created yearly partition %s", name)
