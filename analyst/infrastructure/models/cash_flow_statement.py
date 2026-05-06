"""SQLModel table definition for persisted cash flow statement snapshots."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Optional

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel, UniqueConstraint

from analyst.infrastructure.models.base import AuditMixin


class CashFlowStatementDB(AuditMixin, SQLModel, table=True):  # type: ignore[call-arg,misc]
    """Persistent row backing the `cash_flow_statement` Kafka topic."""

    __tablename__ = "t_cash_flow_statement"
    __table_args__ = (
        UniqueConstraint("composite_key", name="uq_cash_flow_statement_composite_key"),
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
    payload: dict[str, Any] = Field(sa_column=Column(JSON, nullable=False))
