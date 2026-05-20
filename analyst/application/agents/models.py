from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator

from analyst.application.analysis.models import AnalysisVerdict

_DEFAULT_RISK_SUMMARY = (
    "Risk profile is mixed; monitor leverage, liquidity, and free cash flow resilience."
)
_DEFAULT_KEY_RISK = (
    "Signals are mixed; monitor leverage, liquidity, and free cash flow for deterioration."
)
_DEFAULT_KEY_SIGNALS_SUMMARY = (
    "No dominant signal identified; monitor momentum, valuation, and volume changes."
)
_TEXT_PRIORITY_KEYS = (
    "summary",
    "takeaway",
    "conclusion",
    "analysis",
    "signal",
    "key_signal",
    "key_signals_summary",
)


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    return str(value).strip()


def _coerce_to_text(value: Any) -> str:
    if value is None:
        return ""

    if isinstance(value, str):
        return value.strip()

    if isinstance(value, dict):
        for key in _TEXT_PRIORITY_KEYS:
            preferred = value.get(key)
            if isinstance(preferred, str) and preferred.strip():
                return preferred.strip()

        fragments = [_coerce_to_text(item) for item in value.values()]
        return " ".join(fragment for fragment in fragments if fragment)

    if isinstance(value, list):
        fragments = [_coerce_to_text(item) for item in value]
        return " ".join(fragment for fragment in fragments if fragment)

    return _normalize_text(value)


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

    momentum_analysis: str = Field(
        validation_alias=AliasChoices("momentum_analysis", "trend_analysis"),
        description="Paragraph describing the primary trend and momentum.",
    )
    valuation_analysis: str = Field(
        validation_alias=AliasChoices("valuation_analysis", "key_levels"),
        description="Paragraph describing current valuation relative to history.",
    )
    historical_trend_analysis: str = Field(
        description="Paragraph comparing current momentum and valuation against the long-term baseline."
    )
    key_signals_summary: str = Field(
        default=_DEFAULT_KEY_SIGNALS_SUMMARY,
        validation_alias=AliasChoices("key_signals_summary", "summary"),
        description="One sentence summary of the share price action.",
    )

    @field_validator(
        "momentum_analysis",
        "valuation_analysis",
        "historical_trend_analysis",
        "key_signals_summary",
        mode="before",
    )
    @classmethod
    def _coerce_share_price_fields(cls, value: Any) -> str:
        return _coerce_to_text(value)

    @field_validator("key_signals_summary")
    @classmethod
    def _ensure_key_signals_summary(cls, value: str) -> str:
        summary = value.strip()
        if summary:
            return summary

        return _DEFAULT_KEY_SIGNALS_SUMMARY


class FundamentalsOutput(BaseModel):
    """The structured output produced by the FundamentalsAgent."""

    growth_analysis: str = Field(description="Analysis of revenue and earnings growth trends.")
    profitability_analysis: str = Field(description="Analysis of margins and return on equity.")
    summary: str = Field(description="One sentence summary of the company's fundamental health.")


class RiskOutput(BaseModel):
    """The structured output produced by the RiskAgent."""

    key_risks: list[str] = Field(
        default_factory=lambda: [_DEFAULT_KEY_RISK],
        validation_alias=AliasChoices("key_risks", "red_flags"),
        description="A list of the top 3-5 key risks.",
    )
    summary: str = Field(
        default=_DEFAULT_RISK_SUMMARY,
        description="One sentence summary of the overall risk profile.",
    )

    @field_validator("key_risks", mode="before")
    @classmethod
    def _coerce_key_risks(cls, value: Any) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            key_risk = value.strip()
            return [key_risk] if key_risk else []

        if isinstance(value, dict):
            risks = [_normalize_text(item) for item in value.values()]
            return [risk for risk in risks if risk]

        if isinstance(value, list):
            risks = [_normalize_text(item) for item in value]
            return [risk for risk in risks if risk]

        key_risk = _normalize_text(value)
        return [key_risk] if key_risk else []

    @field_validator("key_risks")
    @classmethod
    def _ensure_non_empty_key_risks(cls, value: list[str]) -> list[str]:
        if value:
            return value

        return [_DEFAULT_KEY_RISK]

    @field_validator("summary", mode="before")
    @classmethod
    def _coerce_summary(cls, value: Any) -> str:
        summary = _normalize_text(value)
        if summary:
            return summary

        return _DEFAULT_RISK_SUMMARY


class SynthesizerOutput(BaseModel):
    """The structured output produced by the SynthesizerAgent."""

    report_md: str = Field(description="The final analysis report in Markdown format.")
    verdict: AnalysisVerdict = Field(description="The final investment verdict.")
    conviction: int = Field(description="Conviction level of the verdict (1-5).", ge=1, le=5)
    key_drivers: list[str] = Field(description="Key bullish drivers identified.")
    key_risks: list[str] = Field(description="Key bearish risks identified.")
