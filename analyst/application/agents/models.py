from typing import Any

from pydantic import AliasChoices, BaseModel, Field, field_validator, model_validator

from analyst.application.analysis.models import AnalysisVerdict

_DEFAULT_RISK_SUMMARY = "Risk profile is mixed; monitor leverage, liquidity, and free cash flow resilience."
_VERDICT_ALIASES: dict[str, AnalysisVerdict] = {
    "bull": "bull",
    "buy": "bull",
    "bullish": "bull",
    "bear": "bear",
    "sell": "bear",
    "bearish": "bear",
    "neutral": "neutral",
    "hold": "neutral",
    "mixed": "neutral",
}
_DEFAULT_KEY_RISK = "Signals are mixed; monitor leverage, liquidity, and free cash flow for deterioration."
_DEFAULT_KEY_SIGNALS_SUMMARY = "No dominant signal identified; monitor momentum, valuation, and volume changes."
_DEFAULT_SYNTHESIZER_REPORT_MD = (
    "# Executive Summary\n\nNo report body was generated. Review specialist outputs and rerun analysis."
)
_DEFAULT_SYNTHESIZER_VERDICT: AnalysisVerdict = "neutral"
_DEFAULT_SYNTHESIZER_CONVICTION = 3
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


def _coerce_to_text_list(value: Any) -> list[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [text for item in value if (text := _coerce_to_text(item))]

    if isinstance(value, dict):
        return [text for item in value.values() if (text := _coerce_to_text(item))]

    text_value = _coerce_to_text(value)
    if text_value:
        return [text_value]

    return []


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

    report_md: str = Field(
        default=_DEFAULT_SYNTHESIZER_REPORT_MD,
        description="The final analysis report in Markdown format.",
    )
    verdict: AnalysisVerdict = Field(
        default=_DEFAULT_SYNTHESIZER_VERDICT,
        description="The final investment verdict.",
    )
    conviction: int = Field(
        default=_DEFAULT_SYNTHESIZER_CONVICTION,
        description="Conviction level of the verdict (1-5).",
        ge=1,
        le=5,
    )
    key_drivers: list[str] = Field(
        default_factory=list,
        description="Key bullish drivers identified.",
    )
    key_risks: list[str] = Field(
        default_factory=list,
        description="Key bearish risks identified.",
    )

    @model_validator(mode="before")
    @classmethod
    def _flatten_nested_verdict_payload(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value

        verdict_payload = value.get("verdict")
        if not isinstance(verdict_payload, dict):
            return value

        flattened = dict(value)
        decision = verdict_payload.get("decision") or verdict_payload.get("verdict")
        if decision is not None:
            flattened["verdict"] = decision

        if flattened.get("conviction") is None and verdict_payload.get("conviction") is not None:
            flattened["conviction"] = verdict_payload.get("conviction")

        if flattened.get("key_drivers") is None and verdict_payload.get("key_drivers") is not None:
            flattened["key_drivers"] = verdict_payload.get("key_drivers")

        if flattened.get("key_risks") is None and verdict_payload.get("key_risks") is not None:
            flattened["key_risks"] = verdict_payload.get("key_risks")

        return flattened

    @field_validator("report_md", mode="before")
    @classmethod
    def _coerce_report_md(cls, value: Any) -> str:
        report_md = _coerce_to_text(value)
        if report_md:
            return report_md

        return _DEFAULT_SYNTHESIZER_REPORT_MD

    @field_validator("verdict", mode="before")
    @classmethod
    def _coerce_verdict(cls, value: Any) -> AnalysisVerdict:
        if isinstance(value, dict):
            value = value.get("decision") or value.get("verdict")

        verdict_text = _coerce_to_text(value).lower()
        return _VERDICT_ALIASES.get(verdict_text, _DEFAULT_SYNTHESIZER_VERDICT)

    @field_validator("conviction", mode="before")
    @classmethod
    def _coerce_conviction(cls, value: Any) -> int:
        conviction_value = _DEFAULT_SYNTHESIZER_CONVICTION

        if value is None or isinstance(value, bool):
            conviction_value = _DEFAULT_SYNTHESIZER_CONVICTION

        elif isinstance(value, (int, float)):
            conviction_value = int(value)

        else:
            conviction_text = _coerce_to_text(value).lower()
            if conviction_text.isdigit() or (conviction_text.startswith("-") and conviction_text[1:].isdigit()):
                conviction_value = int(conviction_text)
            elif conviction_text in {"low", "weak"}:
                conviction_value = 1
            elif conviction_text in {"medium", "moderate"}:
                conviction_value = 3
            elif conviction_text in {"high", "strong"}:
                conviction_value = 5

        return max(1, min(5, conviction_value))

    @field_validator("key_drivers", "key_risks", mode="before")
    @classmethod
    def _coerce_key_lists(cls, value: Any) -> list[str]:
        return _coerce_to_text_list(value)
