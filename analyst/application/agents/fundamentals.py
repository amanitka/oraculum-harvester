from pathlib import Path
from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from common.domain.income_statement import StatementVariant

_PROMPT_PATH = Path(__file__).parent / "prompts" / "fundamentals.md"


class FundamentalsOutput(BaseModel):
    """The structured output produced by the FundamentalsAgent."""

    trend_analysis: str = Field(description="Paragraph describing revenue and margin trends.")
    return_on_capital_analysis: str = Field(description="Paragraph analyzing ROCE and asset turnover.")
    summary: str = Field(description="One sentence summary of fundamental health.")


class FundamentalsAgent(Agent[FundamentalsOutput]):
    """
    Agent responsible for analyzing income statement and balance sheet trends.
    """

    name = "Fundamentals"
    output_model = FundamentalsOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[FundamentalsOutput]:
        variant: StatementVariant = ctx.default_variant 

        income_statement_md = ctx.tools.get_income_statement_history(
            ctx.ticker, template=ctx.template, variant=variant
        )
        balance_sheet_md = ctx.tools.get_balance_sheet_history(
            ctx.ticker, template=ctx.template, variant=variant
        )
        derived_metrics_md = ctx.tools.get_derived_metrics(
            ctx.ticker, template=ctx.template, variant=variant
        )

        prompt = self.system_prompt.replace("{{ income_statement }}", income_statement_md)
        prompt = prompt.replace("{{ balance_sheet }}", balance_sheet_md)
        prompt = prompt.replace("{{ derived_metrics }}", derived_metrics_md)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyze fundamentals for {ctx.ticker} as of {ctx.as_of}."},
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=800,
            temperature=0.2,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens
        
        return AgentOutput(result=result, tokens=total_tokens)
