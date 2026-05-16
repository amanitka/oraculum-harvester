from datetime import date, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field

AnalysisStatus = Literal["pending", "running", "completed", "failed"]
"""Defines the possible lifecycle states of an analysis task."""

AnalysisVerdict = Literal["bull", "bear", "neutral"]
"""Defines the possible investment verdicts from an analysis."""


class AnalysisResult(BaseModel):
    """
    Represents the structured output of a ticker analysis workflow.

    This is the core domain model, independent of persistence format. It serves as
    the return type for the main analysis workflow and contains all information
    required by the UI to display the results.
    """

    correlation_id: UUID = Field(
        description="The unique identifier for this analysis run, linking request to result."
    )
    ticker: str = Field(description="The ticker symbol analyzed.")
    market: str = Field(description="The market of the ticker (e.g., 'us').")
    analysis_date: date = Field(
        description="The date for which the analysis was performed, typically 'today'."
    )
    status: AnalysisStatus = Field(description="The current status of the analysis.")

    # Payload fields, populated on completion
    report_md: str | None = Field(
        default=None, description="The final analysis report in Markdown format."
    )
    verdict: AnalysisVerdict | None = Field(
        default=None, description="The final investment verdict."
    )
    conviction: int | None = Field(
        default=None,
        description="Conviction level of the verdict, from 1 (low) to 5 (high).",
        ge=1,
        le=5,
    )
    key_drivers: list[str] = Field(
        default_factory=list, description="Key bullish drivers identified by the workflow."
    )
    key_risks: list[str] = Field(
        default_factory=list, description="Key bearish risks identified by the workflow."
    )

    # Metadata and audit fields
    agent_trace: dict[str, Any] = Field(
        default_factory=dict,
        description="A structured trace of intermediate agent outputs for debugging and audit.",
    )
    token_usage: int = Field(
        default=0, description="Total LLM tokens consumed during the analysis."
    )
    error: str | None = Field(
        default=None, description="Error message if the analysis failed."
    )
    created_at: datetime = Field(
        description="Timestamp (UTC) when the analysis was requested."
    )
    updated_at: datetime = Field(
        description="Timestamp (UTC) when the analysis was last updated."
    )
