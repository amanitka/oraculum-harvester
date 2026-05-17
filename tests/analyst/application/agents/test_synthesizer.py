import pytest
from datetime import date
from pydantic import BaseModel

from analyst.application.agents.context import AgentContext
from analyst.application.agents.synthesizer import SynthesizerAgent
from tests.common.llm.fake_llm_client import FakeLlmClient
from tests.analyst.application.agents.test_fundamentals import FakeDataTools


class DummyOutput(BaseModel):
    summary: str


@pytest.mark.asyncio
async def test_synthesizer_agent_success():
    canned_json = '{"report_md": "# Report\\nGood stock", "verdict": "bull", "conviction": 4, "key_drivers": ["Growth"], "key_risks": ["Debt"]}'
    llm = FakeLlmClient(canned_response_text=canned_json)
    tools = FakeDataTools()

    ctx = AgentContext(
        ticker="AAPL",
        market="us",
        as_of=date.today(),
        template="general",
        default_variant="annual",
        tools=tools,
        llm=llm,
        token_budget=1000,
        prior_outputs={"Fundamentals": DummyOutput(summary="Strong")},
    )

    agent = SynthesizerAgent()
    output = await agent.run(ctx)

    assert output.result.verdict == "bull"
    assert output.result.conviction == 4
    assert len(output.result.key_drivers) == 1
    assert output.tokens == 30
