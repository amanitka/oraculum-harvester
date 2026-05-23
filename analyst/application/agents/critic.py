from pathlib import Path
import json

from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from common.config import config

_PROMPT_PATH = Path(__file__).parent / "prompts" / "critic.md"


class CriticOutput(BaseModel):
    """The structured output produced by the CriticAgent."""

    contradictions_found: list[str] = Field(
        description="A list of contradictions or inconsistencies found between the specialist agent outputs."
    )
    is_consistent: bool = Field(description="A boolean flag indicating whether the analyses are consistent.")


class CriticAgent(Agent[CriticOutput]):
    """
    Agent responsible for identifying contradictions between specialist agent outputs.
    """

    name = "Critic"
    output_model = CriticOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[CriticOutput]:
        # Exclude the FactSheet from the outputs sent to the critic
        specialist_outputs = {name: model for name, model in ctx.prior_outputs.items() if name != "FactSheet"}
        prior_outputs_json = json.dumps(
            {name: model.model_dump() for name, model in specialist_outputs.items()},
            indent=2,
        )

        prompt = self.system_prompt.replace("{{ prior_outputs }}", prior_outputs_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Critique the analysis for {ctx.ticker}. Identify any contradictions between the provided agent summaries.",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="pro-tier",
            max_tokens=config.llm.router_settings.max_tokens,
            temperature=config.llm.router_settings.temperature,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens

        return AgentOutput(result=result, tokens=total_tokens)
