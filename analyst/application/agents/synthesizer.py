import json
from pathlib import Path

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext
from analyst.application.agents.models import SynthesizerOutput
from common.config import config

_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesizer.md"


class SynthesizerAgent(Agent[SynthesizerOutput]):
    """
    Agent responsible for merging all specialist outputs into the final report.
    """

    name = "Synthesizer"
    output_model = SynthesizerOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[SynthesizerOutput]:
        # Exclude FactSheet and Critic from the main prior outputs for synthesis
        specialist_outputs = {
            name: model for name, model in ctx.prior_outputs.items() if name not in ["FactSheet", "Critic"]
        }
        prior_outputs_json = json.dumps(
            {name: model.model_dump() for name, model in specialist_outputs.items()},
            indent=2,
        )

        # Get the critic's output
        critic_output = ctx.prior_outputs.get("Critic")
        critic_report_json = critic_output.model_dump_json(indent=2) if critic_output else "{}"

        prompt = self.system_prompt.replace("{{ prior_outputs }}", prior_outputs_json)
        prompt = prompt.replace("{{ critic_report }}", critic_report_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Synthesize the analysis for {ctx.ticker}. "
                f"The resolved statement template was '{ctx.template}'. "
                f"The default variant was '{ctx.default_variant}'. "
                "Generate the final report and structured verdict, explicitly addressing the critic's findings.",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="specialist-tier",
            max_tokens=config.llm.router_settings.max_tokens,
            temperature=0.3, # Overriding deterministic default for synthesis
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens

        return AgentOutput(result=result, tokens=total_tokens)