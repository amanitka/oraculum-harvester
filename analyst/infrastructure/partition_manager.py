"""Monthly partition manager for ``t_share_price``.

Creates any missing ``RANGE`` partitions from the historical data start date
up to ``months_ahead`` months into the future.  Idempotent: partitions that
already exist are skipped without error.
"""

from __future__ import annotations

import logging
from datetime import date

from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

logger = logging.getLogger(__name__)

_SHARE_PRICE_TABLE = "t_share_price"
_HISTORICAL_START = date(1990, 1, 1)


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


class PartitionManager:
    """Ensures monthly ``RANGE`` partitions of ``t_share_price`` exist."""

    @classmethod
    async def ensure_share_price_partitions(
            cls, session: AsyncSession, months_ahead: int = 9
    ) -> None:
        """Create any missing monthly partitions.

        Covers ``_HISTORICAL_START`` through the current month plus
        ``months_ahead`` additional months (inclusive).
        """
        today_month = _first_of_month(date.today())
        end = _add_months(today_month, months_ahead + 1)

        existing = await cls._existing_partition_names(session)

        current = _first_of_month(_HISTORICAL_START)
        created = 0
        while current < end:
            name = f"{_SHARE_PRICE_TABLE}_{current.year:04d}_{current.month:02d}"
            if name not in existing:
                await cls._create_partition(session, name, current)
                created += 1
            current = _next_month(current)

        total_months = (
                (end.year - _HISTORICAL_START.year) * 12
                + end.month
                - _HISTORICAL_START.month
        )
        logger.info(
            "Share price partition check complete: created=%d total_range_months=%d",
            created,
            total_months,
        )

    @staticmethod
    async def _existing_partition_names(session: AsyncSession) -> set[str]:
        """Return names of existing t_share_price_* partitions."""
        result = await session.execute(
            text(
                "SELECT tablename FROM pg_tables"
                " WHERE schemaname = 'public'"
                " AND tablename LIKE 't_share_price_%'"
            )
        )
        return {row[0] for row in result}

    @staticmethod
    async def _create_partition(
            session: AsyncSession, name: str, month_start: date
    ) -> None:
        """Issue a ``CREATE TABLE IF NOT EXISTS ... PARTITION OF`` statement."""
        month_end = _next_month(month_start)
        await session.exec(
            text(
                f"CREATE TABLE IF NOT EXISTS {name}"
                f" PARTITION OF {_SHARE_PRICE_TABLE}"
                f" FOR VALUES FROM ('{month_start.isoformat()}')"
                f" TO ('{month_end.isoformat()}')"
            )
        )
        logger.debug("Created partition %s", name)
