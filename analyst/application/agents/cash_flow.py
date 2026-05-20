from pathlib import Path
import json

from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from analyst.application.agents.models import FinancialFactSheet
from analyst.application.agents.factsheet import FactSheetOutput
from common.config import config

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
        # Access the pre-compiled fact sheet from the context
        fact_sheet_output: FactSheetOutput = ctx.prior_outputs["FactSheet"]
        fact_sheet: FinancialFactSheet = fact_sheet_output.fact_sheet

        # Prepare the data for the prompt
        prompt_data = {
            "cash_flow_history": fact_sheet.cash_flow_history,
            "derived_metrics": fact_sheet.derived_metrics,
        }
        prompt_data_json = json.dumps(prompt_data, indent=2)

        prompt = self.system_prompt.replace("{{ fact_sheet_json }}", prompt_data_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Analyze cash flow for {ctx.ticker} as of {ctx.as_of} "
                f"based on the provided financial fact sheet.",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=config.llm.max_tokens,
            temperature=0.2,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens

        return AgentOutput(result=result, tokens=total_tokens)
