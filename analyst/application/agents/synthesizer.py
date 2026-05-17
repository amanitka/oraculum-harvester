import json
from pathlib import Path
from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent
from analyst.application.agents.context import AgentContext
from analyst.application.analysis.models import AnalysisVerdict

_PROMPT_PATH = Path(__file__).parent / "prompts" / "synthesizer.md"


class SynthesizerOutput(BaseModel):
    """The structured output produced by the SynthesizerAgent."""

    report_md: str = Field(description="The final analysis report in Markdown format.")
    verdict: AnalysisVerdict = Field(description="The final investment verdict.")
    conviction: int = Field(description="Conviction level of the verdict (1-5).", ge=1, le=5)
    key_drivers: list[str] = Field(description="Key bullish drivers identified.")
    key_risks: list[str] = Field(description="Key bearish risks identified.")


class SynthesizerAgent(Agent[SynthesizerOutput]):
    """
    Agent responsible for merging all specialist outputs into the final report.
    """

    name = "Synthesizer"
    output_model = SynthesizerOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> SynthesizerOutput:
        prior_outputs_json = json.dumps(
            {name: model.model_dump() for name, model in ctx.prior_outputs.items()},
            indent=2,
        )

        prompt = self.system_prompt.replace("{{ prior_outputs }}", prior_outputs_json)

        messages = [
            {"role": "system", "content": prompt},
            {
                "role": "user",
                "content": f"Synthesize the analysis for {ctx.ticker}. "
                f"The resolved statement template was '{ctx.template}'. "
                f"The default variant was '{ctx.default_variant}'. "
                "Generate the final report and structured verdict.",
            },
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-pro",  # Use a more powerful model for the final synthesis
            max_tokens=2048,
            temperature=0.3,
            response_format=self.output_model,
        )

        return self.output_model.model_validate_json(response.text)
