from datetime import date
from typing import Any, Mapping

import pytest
from pydantic import BaseModel

from analyst.application.agents.cash_flow import (
    CashFlowAgent,
    _build_quantitative_guardrails,
)
from analyst.application.agents.context import AgentContext
from analyst.application.agents.factsheet import FactSheetOutput
from analyst.application.agents.models import FinancialFactSheet
from common.llm.base import LlmResponse
from tests.analyst.application.agents.test_fundamentals import FakeDataTools
from tests.common.llm.fake_llm_client import FakeLlmClient


class RecordingFakeLlmClient(FakeLlmClient):
    def __init__(self, canned_response_text: str = "{}") -> None:
        super().__init__(canned_response_text)
        self.last_messages: list[Mapping[str, Any]] = []

    async def complete(
        self,
        messages: list[Mapping[str, Any]],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
        response_format: type[BaseModel] | dict[str, Any] | None = None,
    ) -> LlmResponse:
        self.last_messages = messages
        return await super().complete(
            messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            response_format=response_format,
        )


def _build_cash_flow_history() -> str:
    rows = [
        "| fiscal_year | payload |",
        "| --- | --- |",
        "| 2021 | {'fiscal_year': 2021, 'net_cash_from_operating_activities': 3400, 'free_cash_flow': 301, 'capital_expenditure': 301} |",
        "| 2022 | {'fiscal_year': 2022, 'net_cash_from_operating_activities': 3565, 'free_cash_flow': 450, 'capital_expenditure': 450} |",
        "| 2023 | {'fiscal_year': 2023, 'net_cash_from_operating_activities': 3100, 'free_cash_flow': 546, 'capital_expenditure': 546} |",
        "| 2024 | {'fiscal_year': 2024, 'net_cash_from_operating_activities': 3200, 'free_cash_flow': 636, 'capital_expenditure': 636} |",
        "| 2025 | {'fiscal_year': 2025, 'net_cash_from_operating_activities': 3300, 'free_cash_flow': 1012, 'capital_expenditure': 1012} |",
    ]
    return "\n".join(rows)


def _build_context(llm: FakeLlmClient) -> AgentContext:
    fact_sheet = FinancialFactSheet(
        ticker_profile={"ticker": "AMD"},
        income_statement_history="fake income statement",
        balance_sheet_history="fake balance sheet",
        cash_flow_history=_build_cash_flow_history(),
        derived_metrics="fake metrics",
        share_price_signals='{"recent_daily": [], "historical_monthly": []}',
    )

    return AgentContext(
        ticker="AMD",
        market="us",
        as_of=date.today(),
        template="general",
        default_variant="annual",
        tools=FakeDataTools(),
        llm=llm,
        token_budget=1000,
        prior_outputs={"FactSheet": FactSheetOutput(fact_sheet=fact_sheet)},
    )


def test_build_quantitative_guardrails_extracts_trend_and_scale() -> None:
    guardrails = _build_quantitative_guardrails(_build_cash_flow_history())

    metrics = guardrails["metrics"]
    assert metrics["free_cash_flow"]["trend"] == "increasing"
    assert metrics["capital_expenditure"]["trend"] == "increasing"
    assert metrics["net_cash_from_operating_activities"]["series_millions"][0]["value_millions"] == 3400


@pytest.mark.asyncio
async def test_cash_flow_agent_injects_quantitative_guardrails() -> None:
    canned_json = (
        '{"cash_generation_analysis": "Cash generation improved with stronger free cash flow.", '
        '"capex_intensity_analysis": "Capex expanded with operating cash support.", '
        '"summary": "Cash flow quality is solid."}'
    )
    llm = RecordingFakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    output = await CashFlowAgent().run(ctx)

    assert output.result.summary == "Cash flow quality is solid."
    assert llm.last_messages
    system_prompt = str(llm.last_messages[0]["content"])
    assert "quantitative_guardrails" in system_prompt
    assert '"free_cash_flow"' in system_prompt
    assert '"trend": "increasing"' in system_prompt
