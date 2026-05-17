from pathlib import Path
from datetime import timedelta
from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent
from analyst.application.agents.context import AgentContext
from common.domain.income_statement import StatementVariant

_PROMPT_PATH = Path(__file__).parent / "prompts" / "risk.md"


class RiskOutput(BaseModel):
    """The structured output produced by the RiskAgent."""

    leverage_liquidity_analysis: str = Field(description="Paragraph describing balance sheet health and debt.")
    red_flags: list[str] = Field(description="List of identified red flags.")
    summary: str = Field(description="One sentence summary of risk profile.")


class RiskAgent(Agent[RiskOutput]):
    """
    Agent responsible for identifying red flags and assessing solvency.
    """

    name = "Risk"
    output_model = RiskOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> RiskOutput:
        # Risk typically uses quarterly for more granular volatility tracking
        variant: StatementVariant = "quarterly"

        balance_sheet_md = ctx.tools.get_balance_sheet_history(
            ctx.ticker, template=ctx.template, variant=variant
        )
        derived_metrics_md = ctx.tools.get_derived_metrics(
            ctx.ticker, template=ctx.template, variant=variant
        )
        
        # Longer window for volatility check (e.g. 1 year)
        start_date = ctx.as_of - timedelta(days=365)
        share_prices_md = ctx.tools.get_price_window(ctx.ticker, start_date, ctx.as_of)

        prompt = self.system_prompt.replace("{{ balance_sheet }}", balance_sheet_md)
        prompt = prompt.replace("{{ derived_metrics }}", derived_metrics_md)
        prompt = prompt.replace("{{ share_prices }}", share_prices_md)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyze risk for {ctx.ticker} as of {ctx.as_of}."},
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=800,
            temperature=0.2,
            response_format=self.output_model,
        )

        return self.output_model.model_validate_json(response.text)
