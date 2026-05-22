from pathlib import Path
import json

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from analyst.application.agents.models import FundamentalsOutput, FinancialFactSheet
from analyst.application.agents.factsheet import FactSheetOutput
from common.config import config

_PROMPT_PATH = Path(__file__).parent / "prompts" / "fundamentals.md"


class FundamentalsAgent(Agent[FundamentalsOutput]):
    """
    Agent responsible for analyzing income statement and balance sheet trends.
    """

    name = "Fundamentals"
    output_model = FundamentalsOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[FundamentalsOutput]:
        # Access the pre-compiled fact sheet from the context
        fact_sheet_output: FactSheetOutput = ctx.prior_outputs["FactSheet"]
        fact_sheet: FinancialFactSheet = fact_sheet_output.fact_sheet

        # Prepare the data for the prompt
        prompt_data = {
            "income_statement_history": fact_sheet.income_statement_history,
            "balance_sheet_history": fact_sheet.balance_sheet_history,
            "derived_metrics": fact_sheet.derived_metrics,
        }
        prompt_data_json = json.dumps(prompt_data, indent=2)

        prompt = self.system_prompt.replace("{{ fact_sheet_json }}", prompt_data_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Analyze fundamentals for {ctx.ticker} as of {ctx.as_of} based on the provided financial fact sheet.",
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