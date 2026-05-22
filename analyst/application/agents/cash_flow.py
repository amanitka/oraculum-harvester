import ast
import json
from pathlib import Path
import re
from typing import Any

from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from analyst.application.agents.models import FinancialFactSheet
from analyst.application.agents.factsheet import FactSheetOutput
from common.config import config

_PROMPT_PATH = Path(__file__).parent / "prompts" / "cash_flow.md"
_DIRECTION_EPSILON = 1e-9
_MISSING_NUMERIC_VALUES = {"", "-", "--", "na", "n/a", "nan", "none", "null"}
_METRIC_ALIASES: dict[str, tuple[str, ...]] = {
    "net_cash_from_operating_activities": (
        "net_cash_from_operating_activities",
        "net_cash_from_operating_activities_continuing_operations",
    ),
    "free_cash_flow": ("free_cash_flow",),
    "capital_expenditure": ("capital_expenditure", "capex"),
}
_YEAR_ALIASES = ("fiscal_year", "year")


def _normalize_key(value: str) -> str:
    return value.strip().lower().replace(" ", "_")


def _parse_numeric(value: Any) -> float | None:
    if value is None:
        return None

    if isinstance(value, bool):
        return None

    if isinstance(value, (int, float)):
        return float(value)

    text = str(value).strip()
    if not text:
        return None

    normalized = text.lower().replace(",", "")
    if normalized in _MISSING_NUMERIC_VALUES:
        return None

    match = re.search(r"-?\d+(?:\.\d+)?", normalized)
    if match is None:
        return None

    numeric_value = float(match.group())
    if "trillion" in normalized:
        return numeric_value * 1_000_000
    if "billion" in normalized:
        return numeric_value * 1_000
    return numeric_value


def _parse_payload(payload_raw: str) -> dict[str, Any]:
    raw = payload_raw.strip()
    if not raw:
        return {}

    try:
        parsed_json = json.loads(raw)
        if isinstance(parsed_json, dict):
            return parsed_json
    except json.JSONDecodeError:
        pass

    try:
        parsed_literal = ast.literal_eval(raw)
    except SyntaxError, ValueError:
        return {}

    return parsed_literal if isinstance(parsed_literal, dict) else {}


def _parse_markdown_table(markdown_table: str) -> list[dict[str, str]]:
    lines = [line.strip() for line in markdown_table.splitlines() if line.strip().startswith("|")]
    if len(lines) < 2:
        return []

    headers = [cell.strip() for cell in lines[0].strip("|").split("|")]
    separator_cells = [cell.strip().replace(":", "") for cell in lines[1].strip("|").split("|")]
    has_separator = bool(separator_cells) and all(cell and set(cell) <= {"-"} for cell in separator_cells)
    data_lines = lines[2:] if has_separator else lines[1:]

    rows: list[dict[str, str]] = []
    for line in data_lines:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(headers):
            continue
        rows.append(dict(zip(headers, cells)))
    return rows


def _deduplicate_series(points: list[tuple[int, float]]) -> list[tuple[int, float]]:
    unique_by_year: dict[int, float] = {}
    for year, value in points:
        if year not in unique_by_year:
            unique_by_year[year] = value
    return [(year, unique_by_year[year]) for year in sorted(unique_by_year)]


def _resolve_year(payload: dict[str, Any], row: dict[str, Any]) -> int | None:
    for year_key in _YEAR_ALIASES:
        numeric_year = _parse_numeric(payload.get(year_key, row.get(year_key)))
        if numeric_year is not None:
            return int(numeric_year)
    return None


def _resolve_metric_value(
    aliases: tuple[str, ...],
    payload: dict[str, Any],
    row: dict[str, Any],
) -> float | None:
    for alias in aliases:
        if alias in payload:
            payload_value = _parse_numeric(payload[alias])
            if payload_value is not None:
                return payload_value

        if alias in row:
            row_value = _parse_numeric(row[alias])
            if row_value is not None:
                return row_value

    return None


def _resolve_trend(points: list[tuple[int, float]]) -> str:
    if len(points) < 2:
        return "insufficient_data"

    first_value = points[0][1]
    last_value = points[-1][1]
    if last_value > first_value + _DIRECTION_EPSILON:
        return "increasing"
    if last_value < first_value - _DIRECTION_EPSILON:
        return "decreasing"
    return "flat"


def _build_metric_guardrails(
    series_by_metric: dict[str, list[tuple[int, float]]],
) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    for metric_name, points in series_by_metric.items():
        deduplicated_series = _deduplicate_series(points)
        if not deduplicated_series:
            continue

        metrics[metric_name] = {
            "trend": _resolve_trend(deduplicated_series),
            "series_millions": [
                {"fiscal_year": year, "value_millions": round(value, 3)} for year, value in deduplicated_series
            ],
        }

    return metrics


def _build_quantitative_guardrails(cash_flow_history: str) -> dict[str, Any]:
    series_by_metric: dict[str, list[tuple[int, float]]] = {metric: [] for metric in _METRIC_ALIASES}

    for markdown_row in _parse_markdown_table(cash_flow_history):
        normalized_row = {_normalize_key(str(key)): value for key, value in markdown_row.items()}
        payload_raw = str(normalized_row.get("payload", ""))
        payload = {_normalize_key(str(key)): value for key, value in _parse_payload(payload_raw).items()}

        year = _resolve_year(payload, normalized_row)
        if year is None:
            continue

        for metric_name, aliases in _METRIC_ALIASES.items():
            metric_value = _resolve_metric_value(aliases, payload, normalized_row)
            if metric_value is not None:
                series_by_metric[metric_name].append((year, metric_value))

    metrics = _build_metric_guardrails(series_by_metric)

    if not metrics:
        return {}

    return {
        "unit_convention": (
            "Treat raw cash-flow values as millions of reporting currency unless explicitly labeled otherwise."
        ),
        "metrics": metrics,
    }


class CashFlowOutput(BaseModel):
    """The structured output produced by the CashFlowAgent."""

    cash_generation_analysis: str = Field(description="Paragraph describing FCF and operating cash flow trends.")
    capex_intensity_analysis: str = Field(description="Paragraph analyzing capital expenditures.")
    summary: str = Field(description="One sentence summary of cash flow quality.")


class CashFlowAgent(Agent[CashFlowOutput]):
    """
    Agent responsible for analyzing cash generation quality and capex intensity.
    """

    name = "CashFlow"
    output_model = CashFlowOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[CashFlowOutput]:
        # Access the pre-compiled fact sheet from the context
        fact_sheet_output: FactSheetOutput = ctx.prior_outputs["FactSheet"]
        fact_sheet: FinancialFactSheet = fact_sheet_output.fact_sheet
        quantitative_guardrails = _build_quantitative_guardrails(fact_sheet.cash_flow_history)

        # Prepare the data for the prompt
        prompt_data = {
            "cash_flow_history": fact_sheet.cash_flow_history,
            "derived_metrics": fact_sheet.derived_metrics,
            "quantitative_guardrails": quantitative_guardrails,
        }
        prompt_data_json = json.dumps(prompt_data, indent=2)

        prompt = self.system_prompt.replace("{{ fact_sheet_json }}", prompt_data_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Analyze cash flow for {ctx.ticker} as of {ctx.as_of} based on the provided financial fact sheet.",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=config.llm.max_tokens,
            temperature=0.2,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens

        return AgentOutput(result=result, tokens=total_tokens)
