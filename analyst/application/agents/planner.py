from pathlib import Path

from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant

_PROMPT_PATH = Path(__file__).parent / "prompts" / "planner.md"


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
    valuation_variant: StatementVariant = Field(
        default="ttm", description="The variant to use for valuation analysis."
    )
    risk_variant: StatementVariant = Field(
        default="quarterly", description="The variant to use for risk analysis."
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
        profile = ctx.tools.get_ticker_profile(ctx.ticker) or {}
        resolved_template = ctx.tools.resolve_template(ctx.ticker)
        
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": f"Ticker: {ctx.ticker}\nProfile: {profile}\n"
                f"Resolved Template must be: {resolved_template}\n"
                "Please generate the plan using default variants (annual for fundamentals/cash_flow, ttm for valuation, quarterly for risk).",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=200,
            temperature=0.0,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens
        
        return AgentOutput(result=result, tokens=total_tokens)
