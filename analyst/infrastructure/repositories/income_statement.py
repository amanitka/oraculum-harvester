"""Async persistence gateway for `IncomeStatementDB`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.models.income_statement import IncomeStatementDB
from common.domain.income_statement import (
    IncomeStatement,
    StatementVariant,
    IncomeStatementTemplate,
)


class IncomeStatementRepository:
    """Read/write access to the `t_income_statement` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def fetch_ticker_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int,
    ) -> list[IncomeStatementDB]:
        """Return the most recent income statements for a ticker."""
        statement = (
            select(IncomeStatementDB)
            .where(IncomeStatementDB.ticker == ticker)
            .where(IncomeStatementDB.template == template)
            .where(IncomeStatementDB.variant == variant)
            .order_by(
                IncomeStatementDB.fiscal_year.desc(),
                IncomeStatementDB.fiscal_period.desc(),
                IncomeStatementDB.report_date.desc(),
            )
            .limit(limit)
        )
        result = await self._session.exec(statement)
        return list(result.all())

    async def upsert(self, statement: IncomeStatement) -> IncomeStatementDB:
        """Insert or fully refresh the row keyed by `composite_key`."""
        existing = await self._find(statement.composite_key)
        payload = statement.model_dump(mode="json")
        row_payload = {
            "composite_key": statement.composite_key,
            "ticker": statement.ticker,
            "simfin_id": statement.simfin_id,
            "template": statement.template,
            "variant": statement.variant,
            "currency": statement.currency,
            "fiscal_year": statement.fiscal_year,
            "fiscal_period": statement.fiscal_period,
            "report_date": statement.report_date,
            "publish_date": statement.publish_date,
            "restated_date": statement.restated_date,
            "extracted_at": statement.extracted_at,
            "payload": payload,
        }
        if existing is None:
            row = IncomeStatementDB(**row_payload)
            self._session.add(row)
        else:
            for key, value in row_payload.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            row = existing
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def _find(self, composite_key: str) -> Optional[IncomeStatementDB]:
        stmt = select(IncomeStatementDB).where(
            IncomeStatementDB.composite_key == composite_key,
        )
        result = await self._session.exec(stmt)
        return result.first()
