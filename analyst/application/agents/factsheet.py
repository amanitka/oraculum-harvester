from pathlib import Path
from datetime import timedelta
from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from analyst.application.agents.models import FinancialFactSheet
from common.domain.income_statement import StatementVariant

_PROMPT_PATH = Path(__file__).parent / "prompts" / "factsheet.md"


class FactSheetOutput(BaseModel):
    """The structured output produced by the FactSheetAgent."""

    fact_sheet: FinancialFactSheet = Field(description="The compiled financial fact sheet.")


class FactSheetAgent(Agent[FactSheetOutput]):
    """
    Agent responsible for compiling a comprehensive financial fact sheet for a given ticker.
    This agent fetches all necessary data and structures it into a FinancialFactSheet model.
    """

    name = "FactSheet"
    output_model = FactSheetOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[FactSheetOutput]:
        # Fetch all necessary data using DataTools
        ticker_profile = await ctx.tools.get_ticker_profile(ctx.ticker)

        # Use the default variant from context for historical statements
        variant: StatementVariant = ctx.default_variant

        income_statement_history = await ctx.tools.get_income_statement_history(
            ctx.ticker, template=ctx.template, variant=variant
        )
        balance_sheet_history = await ctx.tools.get_balance_sheet_history(
            ctx.ticker, template=ctx.template, variant=variant
        )
        cash_flow_history = await ctx.tools.get_cash_flow_history(
            ctx.ticker, template=ctx.template, variant=variant
        )
        derived_metrics = await ctx.tools.get_derived_metrics(
            ctx.ticker, template=ctx.template, variant=variant
        )
        share_price_signals = await ctx.tools.get_share_price_signals(
            ctx.ticker, ctx.market, ctx.as_of
        )

        fact_sheet = FinancialFactSheet(
            ticker_profile=ticker_profile if ticker_profile else {},
            income_statement_history=income_statement_history,
            balance_sheet_history=balance_sheet_history,
            cash_flow_history=cash_flow_history,
            derived_metrics=derived_metrics,
            share_price_signals=share_price_signals,
        )

        # The FactSheetAgent itself doesn't perform LLM analysis, so no LLM call here.
        # The output is purely the compiled data.
        return AgentOutput(result=FactSheetOutput(fact_sheet=fact_sheet), tokens=0)