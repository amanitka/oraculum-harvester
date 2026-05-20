from pydantic import BaseModel, Field

from analyst.application.analysis.models import AnalysisVerdict


class FinancialFactSheet(BaseModel):
    """
    A single, immutable source of truth for all financial data for a given analysis.
    This is created by the FactSheetAgent and used by all other specialist agents.
    """

    ticker_profile: dict[str, str]
    income_statement_history: str
    balance_sheet_history: str
    cash_flow_history: str
    derived_metrics: str
    share_price_signals: str


class ValuationOutput(BaseModel):
    """The structured output produced by the ValuationAgent."""

    multiple_analysis: str = Field(description="Paragraph describing current multiples vs history.")
    summary: str = Field(description="One sentence summary of valuation.")


class SharePriceOutput(BaseModel):
    """The structured output produced by the SharePriceAgent."""

    trend_analysis: str = Field(description="Paragraph describing the primary trend and momentum.")
    key_levels: str = Field(description="Key support and resistance levels.")
    summary: str = Field(description="One sentence summary of the share price action.")


class FundamentalsOutput(BaseModel):
    """The structured output produced by the FundamentalsAgent."""

    growth_analysis: str = Field(description="Analysis of revenue and earnings growth trends.")
    profitability_analysis: str = Field(description="Analysis of margins and return on equity.")
    summary: str = Field(description="One sentence summary of the company's fundamental health.")


class RiskOutput(BaseModel):
    """The structured output produced by the RiskAgent."""

    key_risks: list[str] = Field(description="A list of the top 3-5 key risks.")
    summary: str = Field(description="One sentence summary of the overall risk profile.")


class SynthesizerOutput(BaseModel):
    """The structured output produced by the SynthesizerAgent."""

    report_md: str = Field(description="The final analysis report in Markdown format.")
    verdict: AnalysisVerdict = Field(description="The final investment verdict.")
    conviction: int = Field(description="Conviction level of the verdict (1-5).", ge=1, le=5)
    key_drivers: list[str] = Field(description="Key bullish drivers identified.")
    key_risks: list[str] = Field(description="Key bearish risks identified.")
