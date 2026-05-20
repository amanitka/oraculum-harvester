import pytest
from datetime import date

from analyst.application.agents.context import AgentContext
from analyst.application.agents.share_price_signals import SharePriceSignalsAgent
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant
from tests.common.llm.fake_llm_client import FakeLlmClient

class FakeDataTools:
    def get_ticker_profile(self, ticker: str) -> dict[str, str] | None:
        return {"ticker": ticker}

    def resolve_template(self, ticker: str) -> IncomeStatementTemplate:
        return "general"

    def get_income_statement_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return ""

    def get_balance_sheet_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return ""

    def get_cash_flow_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return ""

    def get_price_window(self, ticker: str, start: date, end: date) -> str:
        return ""

    def get_derived_metrics(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return ""

    async def get_share_price_signals(self, ticker: str, market: str, as_of: date) -> str:
        return '{"recent_daily": [], "historical_monthly": []}'


@pytest.mark.asyncio
async def test_share_price_signals_agent_success():
    canned_json = '{"momentum_analysis": "Strong", "valuation_analysis": "Cheap", "historical_trend_analysis": "Below avg", "key_signals_summary": "Buy now."}'
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
        prior_outputs={},
    )

    agent = SharePriceSignalsAgent()
    output = await agent.run(ctx)

    assert output.result.key_signals_summary == "Buy now."
    assert output.tokens == 30
