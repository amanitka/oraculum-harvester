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


@pytest.mark.asyncio
async def test_synthesizer_agent_accepts_nested_verdict_payload() -> None:
    canned_json = (
        '{"report_md": "# AMD Investment View\\n\\nBalanced setup.", '
        '"verdict": {"decision": "Hold", "conviction": 4, '
        '"key_drivers": ["AI demand remains robust."], '
        '"key_risks": ["Valuation remains elevated."]}}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    tools = FakeDataTools()

    ctx = AgentContext(
        ticker="AMD",
        market="us",
        as_of=date.today(),
        template="general",
        default_variant="annual",
        tools=tools,
        llm=llm,
        token_budget=1000,
        prior_outputs={"Fundamentals": DummyOutput(summary="Mixed")},
    )

    output = await SynthesizerAgent().run(ctx)

    assert output.result.verdict == "neutral"
    assert output.result.conviction == 4
    assert output.result.key_drivers == ["AI demand remains robust."]
    assert output.result.key_risks == ["Valuation remains elevated."]


@pytest.mark.asyncio
async def test_synthesizer_agent_uses_defaults_for_missing_nested_fields() -> None:
    canned_json = '{"report_md": "", "verdict": {"decision": "unknown"}}'
    llm = FakeLlmClient(canned_response_text=canned_json)
    tools = FakeDataTools()

    ctx = AgentContext(
        ticker="AMD",
        market="us",
        as_of=date.today(),
        template="general",
        default_variant="annual",
        tools=tools,
        llm=llm,
        token_budget=1000,
        prior_outputs={"Fundamentals": DummyOutput(summary="Mixed")},
    )

    output = await SynthesizerAgent().run(ctx)

    assert output.result.verdict == "neutral"
    assert output.result.conviction == 3
    assert output.result.key_drivers == []
    assert output.result.key_risks == []
    assert output.result.report_md.startswith("# Executive Summary")
