from pathlib import Path

from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant
from common.config import config

_PROMPT_PATH = Path(__file__).parent / "prompts" / "planner.md"
_DEFAULT_ANALYSIS_FOCUS = "Prioritize recent momentum shifts, valuation dislocations, and unusual volume signals."


class PlannerPlan(BaseModel):
    """The structured output produced by the PlannerAgent."""

    template: IncomeStatementTemplate = Field(
        description="The resolved statement template based on the ticker's industry."
    )
    fundamentals_variant: StatementVariant = Field(
        default="annual", description="The variant to use for fundamental analysis."
    )
    cash_flow_variant: StatementVariant = Field(
        default="annual", description="The variant to use for cash flow analysis."
    )
    valuation_variant: StatementVariant = Field(default="ttm", description="The variant to use for valuation analysis.")
    risk_variant: StatementVariant = Field(default="quarterly", description="The variant to use for risk analysis.")
    analysis_focus: str = Field(
        default=_DEFAULT_ANALYSIS_FOCUS,
        description="A one-sentence description of what to focus on, based on recent share price signals.",
    )


class PlannerAgent(Agent[PlannerPlan]):
    """
    Agent responsible for resolving the statement template and variants for the analysis run.
    """

    name = "Planner"
    output_model = PlannerPlan

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[PlannerPlan]:
        profile = await ctx.tools.get_ticker_profile(ctx.ticker) or {}
        resolved_template = await ctx.tools.resolve_template(ctx.ticker)
        share_price_signals = await ctx.tools.get_share_price_signals(ctx.ticker, ctx.market, ctx.as_of)

        prompt = self.system_prompt.replace("{{ market_signals_json }}", share_price_signals)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Ticker: {ctx.ticker}\nProfile: {profile}\n"
                f"Resolved Template must be: {resolved_template}\n"
                "Please generate the plan using default variants (annual for fundamentals/cash_flow, ttm for valuation, quarterly for risk), "
                "and set an analysis focus based on the market signals.",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="flash-tier",
            max_tokens=config.llm.router_settings.max_tokens,
            temperature=config.llm.router_settings.temperature,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens

        return AgentOutput(result=result, tokens=total_tokens)