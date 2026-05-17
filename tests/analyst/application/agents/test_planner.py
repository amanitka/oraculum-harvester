import pytest
from datetime import date

from analyst.application.agents.context import AgentContext
from analyst.application.agents.planner import PlannerAgent
from tests.common.llm.fake_llm_client import FakeLlmClient
from tests.analyst.application.agents.test_fundamentals import FakeDataTools


@pytest.mark.asyncio
async def test_planner_agent_success():
    canned_json = '{"template": "banks", "fundamentals_variant": "annual", "cash_flow_variant": "annual", "valuation_variant": "ttm", "risk_variant": "quarterly"}'
    llm = FakeLlmClient(canned_response_text=canned_json)
    tools = FakeDataTools()

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
    assert output.tokens == 30
