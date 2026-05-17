from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Index
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Column, Field, SQLModel, Text


class AnalysisDB(SQLModel, table=True):
    """
    Represents a row in the `t_analysis` table, storing the state and result
    of a ticker analysis task.
    """

    __tablename__ = "t_analysis"
    __table_args__ = (
        Index("ix_analysis_correlation_id", "correlation_id", unique=True),
        Index("ix_analysis_ticker_market_created", "ticker", "market", "created_at"),
        Index("ix_analysis_status_created", "status", "created_at"),
    )

    id: int | None = Field(default=None, primary_key=True)
    correlation_id: UUID = Field(description="The unique ID of the analysis run, linking to the request.")
    ticker: str = Field(description="The ticker symbol analyzed.")
    market: str = Field(description="The market of the ticker (e.g., 'us').")
    analysis_date: date = Field(description="The date for which the analysis was performed.")
    status: str = Field(description="The current status of the analysis (pending, running, completed, failed).")

    # Result payload, populated on completion
    report_md: str | None = Field(default=None, sa_column=Column(Text), description="The final analysis report in Markdown format.")
    verdict: str | None = Field(default=None, description="The final investment verdict (bull, bear, neutral).")
    conviction: int | None = Field(default=None, description="Conviction level of the verdict (1-5).")
    payload: dict[str, Any] | None = Field(default=None, sa_column=Column(JSONB), description="Full structured result including per-agent traces.")
    error: str | None = Field(default=None, sa_column=Column(Text), description="Error message if the analysis failed.")

    # Timestamps
    created_at: datetime = Field(description="Timestamp (UTC) when the analysis was requested.")
    updated_at: datetime = Field(description="Timestamp (UTC) when the analysis was last updated.")
