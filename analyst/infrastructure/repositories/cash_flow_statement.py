"""Async persistence gateway for `CashFlowStatementDB`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.models.cash_flow_statement import CashFlowStatementDB
from common.domain.cash_flow_statement import CashFlowStatement


class CashFlowStatementRepository:
    """Read/write access to the `t_cash_flow_statement` table."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, statement: CashFlowStatement) -> CashFlowStatementDB:
        """Insert or fully refresh the row keyed by `composite_key`."""
        existing = await self._find(statement.composite_key)
        payload = statement.model_dump(mode="json")
        row_payload = {
            "composite_key": statement.composite_key,
            "ticker": statement.ticker,
            "simfin_id": statement.simfin_id,
            "template": statement.template,
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
            row = CashFlowStatementDB(**row_payload)
            self._session.add(row)
        else:
            for key, value in row_payload.items():
                setattr(existing, key, value)
            existing.updated_at = datetime.now(timezone.utc)
            row = existing
        await self._session.commit()
        await self._session.refresh(row)
        return row

    async def _find(self, composite_key: str) -> Optional[CashFlowStatementDB]:
        stmt = select(CashFlowStatementDB).where(
            CashFlowStatementDB.composite_key == composite_key,
        )
        result = await self._session.exec(stmt)
        return result.first()
