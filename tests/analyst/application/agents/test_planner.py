from datetime import date

import pytest

from analyst.application.agents.context import AgentContext
from analyst.application.agents.planner import PlannerAgent
from tests.common.llm.fake_llm_client import FakeLlmClient
from tests.analyst.application.agents.test_fundamentals import FakeDataTools


class FakePlannerDataTools(FakeDataTools):
    async def get_share_price_signals(self, ticker: str, market: str, as_of: date) -> str:
        return '{"recent_daily": [], "historical_monthly": []}'


@pytest.mark.asyncio
async def test_planner_agent_success():
    canned_json = (
        '{"template": "banks", "fundamentals_variant": "annual", '
        '"cash_flow_variant": "annual", "valuation_variant": "ttm", '
        '"risk_variant": "quarterly", "analysis_focus": "Monitor valuation compression after a momentum breakout."}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    tools = FakePlannerDataTools()

    ctx = AgentContext(
        ticker="JPM",
        market="us",
        as_of=date.today(),
        template="general",
        default_variant="annual",
        tools=tools,
        llm=llm,
        token_budget=1000,
        prior_outputs={},
    )

    agent = PlannerAgent()
    output = await agent.run(ctx)

    assert output.result.template == "banks"
    assert output.result.analysis_focus
    assert output.tokens == 30


@pytest.mark.asyncio
async def test_planner_agent_uses_default_analysis_focus_when_missing_from_llm():
    canned_json = (
        '{"template": "banks", "fundamentals_variant": "annual", '
        '"cash_flow_variant": "annual", "valuation_variant": "ttm", '
        '"risk_variant": "quarterly"}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    tools = FakePlannerDataTools()

    ctx = AgentContext(
        ticker="JPM",
        market="us",
        as_of=date.today(),
        template="general",
        default_variant="annual",
        tools=tools,
        llm=llm,
        token_budget=1000,
        prior_outputs={},
    )

    agent = PlannerAgent()
    output = await agent.run(ctx)

    assert output.result.analysis_focus == (
        "Prioritize recent momentum shifts, valuation dislocations, and unusual volume signals."
    )
