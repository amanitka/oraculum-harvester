from pathlib import Path
from pydantic import BaseModel, Field

from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext

_PROMPT_PATH = Path(__file__).parent / "prompts" / "share_price.md"


class SharePriceOutput(BaseModel):
    """The structured output produced by the SharePriceAgent."""

    momentum_analysis: str = Field(description="Paragraph analyzing recent price momentum, using moving averages and volume velocity.")
    valuation_analysis: str = Field(description="Paragraph analyzing the current valuation based on PE, P/FCF, and P/B ratios.")
    historical_trend_analysis: str = Field(description="Paragraph comparing current valuation and momentum to the 10-year historical baseline.")
    key_signals_summary: str = Field(description="One-sentence summary of the most critical signals observed (e.g., Graham Net-Net, high volume).")


class SharePriceAgent(Agent[SharePriceOutput]):
    """
    Agent responsible for analyzing daily market signals and historical monthly signals.
    """

    name = "SharePrice"
    output_model = SharePriceOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[SharePriceOutput]:
        signals_json = await ctx.tools.get_share_price_signals(ctx.ticker, ctx.market, ctx.as_of)

        prompt = self.system_prompt.replace("{{ market_signals_json }}", signals_json)

        messages = [
            {"role": "system", "content": prompt},
            {"role": "user", "content": f"Analyze the market signals for {ctx.ticker} as of {ctx.as_of}."},
        ]

        response = await ctx.llm.complete(
            messages=messages,
            model="gemini-2.5-flash-lite",
            max_tokens=1024,
            temperature=0.2,
            response_format=self.output_model,
        )

        result = self.output_model.model_validate_json(response.text)
        total_tokens = response.input_tokens + response.output_tokens

        return AgentOutput(result=result, tokens=total_tokens)
