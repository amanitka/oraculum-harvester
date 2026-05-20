from datetime import date

import pytest

from analyst.application.agents.context import AgentContext
from analyst.application.agents.factsheet import FactSheetOutput
from analyst.application.agents.fundamentals import FundamentalsAgent
from analyst.application.agents.models import FinancialFactSheet
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant
from tests.common.llm.fake_llm_client import FakeLlmClient


class FakeDataTools:
    async def get_ticker_profile(self, ticker: str) -> dict[str, str] | None:
        return {"ticker": ticker}

    async def resolve_template(self, ticker: str) -> IncomeStatementTemplate:
        return "general"

    async def get_income_statement_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return "fake income statement"

    async def get_balance_sheet_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return "fake balance sheet"

    async def get_cash_flow_history(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return "fake cash flow"

    async def get_price_window(self, ticker: str, start: date, end: date) -> str:
        return "fake prices"

    async def get_derived_metrics(
        self, ticker: str, *, template: IncomeStatementTemplate, variant: StatementVariant, limit: int = 100
    ) -> str:
        return "fake metrics"


def _build_context(llm: FakeLlmClient) -> AgentContext:
    fact_sheet = FinancialFactSheet(
        ticker_profile={"ticker": "AAPL"},
        income_statement_history="fake income statement",
        balance_sheet_history="fake balance sheet",
        cash_flow_history="fake cash flow",
        derived_metrics="fake metrics",
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
async def test_fundamentals_agent_success():
    canned_json = (
        '{"growth_analysis": "Revenue and earnings growth remain steady.", '
        '"profitability_analysis": "Margins and returns remain healthy.", '
        '"summary": "Strong business."}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    agent = FundamentalsAgent()
    output = await agent.run(ctx)

    assert output.result.summary == "Strong business."
    assert output.tokens == 30
