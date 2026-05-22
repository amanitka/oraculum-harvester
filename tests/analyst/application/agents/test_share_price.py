from datetime import date

import pytest

from analyst.application.agents.context import AgentContext
from analyst.application.agents.factsheet import FactSheetOutput
from analyst.application.agents.models import FinancialFactSheet
from analyst.application.agents.share_price import SharePriceAgent
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant
from tests.common.llm.fake_llm_client import FakeLlmClient


_DEFAULT_KEY_SIGNALS_SUMMARY = "No dominant signal identified; monitor momentum, valuation, and volume changes."


class FakeDataTools:
    def get_ticker_profile(self, ticker: str) -> dict[str, str] | None:
        return {"ticker": ticker}

    def resolve_template(self, ticker: str) -> IncomeStatementTemplate:
        return "general"

    def get_income_statement_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        return ""

    def get_balance_sheet_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        return ""

    def get_cash_flow_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        return ""

    def get_price_window(self, ticker: str, start: date, end: date) -> str:
        return ""

    def get_derived_metrics(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        return ""

    async def get_share_price_signals(self, ticker: str, market: str, as_of: date) -> str:
        return '{"recent_daily": [], "historical_monthly": []}'


def _build_context(llm: FakeLlmClient) -> AgentContext:
    fact_sheet = FinancialFactSheet(
        ticker_profile={"ticker": "AAPL"},
        income_statement_history="",
        balance_sheet_history="",
        cash_flow_history="",
        derived_metrics="",
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
async def test_share_price_signals_agent_success():
    canned_json = '{"momentum_analysis": "Strong", "valuation_analysis": "Cheap", "historical_trend_analysis": "Below avg", "key_signals_summary": "Buy now."}'
    llm = FakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    agent = SharePriceAgent()
    output = await agent.run(ctx)

    assert output.result.key_signals_summary == "Buy now."
    assert output.tokens == 30


@pytest.mark.asyncio
async def test_share_price_signals_agent_coerces_nested_fields_and_default_summary():
    canned_json = (
        '{"momentum_analysis": {"recent_trend": "Momentum remains positive."}, '
        '"valuation_analysis": {"recent_valuation": {"summary": "Valuation is rich versus history."}}, '
        '"historical_trend_analysis": {"historical_comparison": "Current multiples are above long-term averages."}}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    agent = SharePriceAgent()
    output = await agent.run(ctx)

    assert output.result.momentum_analysis == "Momentum remains positive."
    assert output.result.valuation_analysis == "Valuation is rich versus history."
    assert output.result.historical_trend_analysis == "Current multiples are above long-term averages."
    assert output.result.key_signals_summary == _DEFAULT_KEY_SIGNALS_SUMMARY


@pytest.mark.asyncio
async def test_share_price_signals_agent_accepts_legacy_keys() -> None:
    canned_json = (
        '{"trend_analysis": "Trend remains constructive.", "key_levels": "Valuation looks stretched.", '
        '"historical_trend_analysis": "Current setup is stronger than long-run median.", '
        '"summary": "Signals are broadly bullish but valuation needs monitoring."}'
    )
    llm = FakeLlmClient(canned_response_text=canned_json)
    ctx = _build_context(llm)

    output = await SharePriceAgent().run(ctx)

    assert output.result.momentum_analysis == "Trend remains constructive."
    assert output.result.valuation_analysis == "Valuation looks stretched."
    assert output.result.historical_trend_analysis == "Current setup is stronger than long-run median."
    assert output.result.key_signals_summary == "Signals are broadly bullish but valuation needs monitoring."
