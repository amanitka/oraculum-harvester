import pytest
from datetime import date

from analyst.application.agents.context import AgentContext
from analyst.application.agents.fundamentals import FundamentalsAgent
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
        return "fake income statement"

    def get_balance_sheet_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return "fake balance sheet"

    def get_cash_flow_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return "fake cash flow"

    def get_price_window(self, ticker: str, start: date, end: date) -> str:
        return "fake prices"

    def get_derived_metrics(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return "fake metrics"


@pytest.mark.asyncio
async def test_fundamentals_agent_success():
    canned_json = '{"trend_analysis": "Good trends", "return_on_capital_analysis": "High ROCE", "summary": "Strong business."}'
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

    agent = FundamentalsAgent()
    output = await agent.run(ctx)

    assert output.result.summary == "Strong business."
    assert output.tokens == 30 # 10 in + 20 out
