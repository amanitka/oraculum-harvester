from pathlib import Path
import json
from typing import Any

from pydantic import Field, field_validator

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from analyst.application.agents.models import SharePriceOutput, FinancialFactSheet
from analyst.application.agents.factsheet import FactSheetOutput

_PROMPT_PATH = Path(__file__).parent / "prompts" / "share_price.md"
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

    return str(value)


class SharePriceAgent(Agent[SharePriceOutput]):
    """
    Agent responsible for analyzing daily market signals and historical monthly signals.
    """

    name = "SharePrice"
    output_model = SharePriceOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[SharePriceOutput]:
        # Access the pre-compiled fact sheet from the context
        fact_sheet_output: FactSheetOutput = ctx.prior_outputs["FactSheet"]
        fact_sheet: FinancialFactSheet = fact_sheet_output.fact_sheet

        signals_json = fact_sheet.share_price_signals

        prompt = self.system_prompt.replace("{{ market_signals_json }}", signals_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Analyze the market signals for {ctx.ticker} as of {ctx.as_of} "
                f"based on the provided financial fact sheet.",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=1024,
            temperature=0.2,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens

        return AgentOutput(result=result, tokens=total_tokens)
