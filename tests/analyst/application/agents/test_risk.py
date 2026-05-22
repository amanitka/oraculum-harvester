from datetime import date

import pytest

from analyst.application.agents.context import AgentContext
from analyst.application.agents.factsheet import FactSheetOutput
from analyst.application.agents.models import FinancialFactSheet
from analyst.application.agents.risk import RiskAgent
from tests.analyst.application.agents.test_fundamentals import FakeDataTools
from tests.common.llm.fake_llm_client import FakeLlmClient

_DEFAULT_KEY_RISK = "Signals are mixed; monitor leverage, liquidity, and free cash flow for deterioration."
_DEFAULT_RISK_SUMMARY = "Risk profile is mixed; monitor leverage, liquidity, and free cash flow resilience."


def _build_context(llm: FakeLlmClient) -> AgentContext:
    fact_sheet = FinancialFactSheet(
        ticker_profile={"ticker": "AAPL"},
        income_statement_history="",
        balance_sheet_history="fake balance sheet",
        cash_flow_history="",
        derived_metrics="fake derived metrics",
        share_price_signals='{"recent_daily": [], "historical_monthly": []}',
    )

    return AgentContext(
        ticker="AAPL",
        market="us",
        as_of=date.today(),
        template="general",
        default_variant="annual",
        tools=FakeDataTools(),
        llm=llm,
        token_budget=1000,
        prior_outputs={"FactSheet": FactSheetOutput(fact_sheet=fact_sheet)},
    )


@pytest.mark.asyncio
async def test_risk_agent_success() -> None:
    canned_json = (
        '{"key_risks": ["Debt has risen faster than equity.", "Free cash flow remains negative.", '
        '"Current ratio has weakened over recent periods."], "summary": "Risk profile is elevated due to weaker liquidity and funding pressure."}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    output = await RiskAgent().run(ctx)

    assert len(output.result.key_risks) == 3
    assert output.result.summary == ("Risk profile is elevated due to weaker liquidity and funding pressure.")
    assert output.tokens == 30


@pytest.mark.asyncio
async def test_risk_agent_uses_default_key_risks_when_missing_from_llm() -> None:
    canned_json = (
        '{"leverage_liquidity_analysis": "Debt climbed while cash balances declined.", '
        '"summary": "Risk is elevated if refinancing conditions tighten."}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    output = await RiskAgent().run(ctx)

    assert output.result.key_risks == [_DEFAULT_KEY_RISK]
    assert output.result.summary == "Risk is elevated if refinancing conditions tighten."


@pytest.mark.asyncio
async def test_risk_agent_accepts_legacy_red_flags_and_default_summary() -> None:
    canned_json = '{"red_flags": ["Debt burden is trending higher.", "Cash reserves are declining."], "summary": ""}'
    llm = FakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    output = await RiskAgent().run(ctx)

    assert output.result.key_risks == [
        "Debt burden is trending higher.",
        "Cash reserves are declining.",
    ]
    assert output.result.summary == _DEFAULT_RISK_SUMMARY
