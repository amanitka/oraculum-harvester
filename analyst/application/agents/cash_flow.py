from pathlib import Path
from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from common.domain.income_statement import StatementVariant

_PROMPT_PATH = Path(__file__).parent / "prompts" / "cash_flow.md"


class CashFlowOutput(BaseModel):
    """The structured output produced by the CashFlowAgent."""

    cash_generation_analysis: str = Field(description="Paragraph describing FCF and operating cash flow trends.")
    capex_intensity_analysis: str = Field(description="Paragraph analyzing capital expenditures.")
    summary: str = Field(description="One sentence summary of cash flow quality.")


class CashFlowAgent(Agent[CashFlowOutput]):
    """
    Agent responsible for analyzing cash generation quality and capex intensity.
    """

    name = "CashFlow"
    output_model = CashFlowOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[CashFlowOutput]:
        variant: StatementVariant = ctx.default_variant

        cash_flow_md = ctx.tools.get_cash_flow_history(
            ctx.ticker, template=ctx.template, variant=variant
        )
        derived_metrics_md = ctx.tools.get_derived_metrics(
            ctx.ticker, template=ctx.template, variant=variant
        )

        prompt = self.system_prompt.replace("{{ cash_flow_statement }}", cash_flow_md)
        prompt = prompt.replace("{{ derived_metrics }}", derived_metrics_md)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyze cash flow for {ctx.ticker} as of {ctx.as_of}."},
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
