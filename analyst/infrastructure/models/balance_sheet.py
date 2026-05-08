"""SQLModel table definition for persisted balance sheet snapshots."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel, UniqueConstraint

from analyst.infrastructure.models.base import AuditMixin


class BalanceSheetDB(AuditMixin, SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Persistent row backing the `balance_sheet` Kafka topic."""

    __tablename__ = "t_balance_sheet"
    __table_args__ = (
        UniqueConstraint("composite_key", name="uq_balance_sheet_composite_key"),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    composite_key: str = Field(index=True)
    ticker: str = Field(index=True)
    simfin_id: int = Field(index=True)
    template: str
    variant: str = Field(index=True)
    currency: str
    fiscal_year: int
    fiscal_period: str
    report_date: date
    publish_date: date
    restated_date: Optional[date] = None
    extracted_at: datetime
    payload: dict[str, Any] = Field(sa_column=Column(JSONB, nullable=False))
