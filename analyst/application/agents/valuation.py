from pathlib import Path
from datetime import timedelta
from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent
from analyst.application.agents.context import AgentContext
from common.domain.income_statement import StatementVariant

_PROMPT_PATH = Path(__file__).parent / "prompts" / "valuation.md"


class ValuationOutput(BaseModel):
    """The structured output produced by the ValuationAgent."""

    multiple_analysis: str = Field(description="Paragraph describing current multiples vs history.")
    summary: str = Field(description="One sentence summary of valuation.")


class ValuationAgent(Agent[ValuationOutput]):
    """
    Agent responsible for analyzing valuation multiples vs history.
    """

    name = "Valuation"
    output_model = ValuationOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> ValuationOutput:
        # Valuation typically uses TTM by default
        variant: StatementVariant = "ttm"

        derived_metrics_md = ctx.tools.get_derived_metrics(
            ctx.ticker, template=ctx.template, variant=variant
        )
        
        # Simple window for recent prices (e.g. last 30 days)
        start_date = ctx.as_of - timedelta(days=30)
        share_prices_md = ctx.tools.get_price_window(ctx.ticker, start_date, ctx.as_of)

        prompt = self.system_prompt.replace("{{ derived_metrics }}", derived_metrics_md)
        prompt = prompt.replace("{{ share_prices }}", share_prices_md)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyze valuation for {ctx.ticker} as of {ctx.as_of}."},
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=800,
            temperature=0.2,
            response_format=self.output_model,
        )

        return self.output_model.model_validate_json(response.text)
