# Implementation Plan: DailySignalsAgent

This document provides a detailed, step-by-step plan for creating and integrating the `DailySignalsAgent`. This agent will be responsible for analyzing recent market data from the `v_daily_market_signals` view and providing insights on technical momentum, valuation, and key trading signals.

The implementation will closely follow the existing `FundamentalsAgent` pattern to ensure architectural consistency.

---

## Step 1: Create the Agent Output Model

First, define the structured output that the `DailySignalsAgent` will produce. This Pydantic model will enforce the agent's response format.

**File:** `analyst/application/agents/daily_signals.py`

```python
from pydantic import BaseModel, Field

class DailySignalsOutput(BaseModel):
    """The structured output produced by the DailySignalsAgent."""

    momentum_analysis: str = Field(description="Paragraph analyzing recent price momentum, using moving averages and volume velocity.")
    valuation_analysis: str = Field(description="Paragraph analyzing the current valuation based on PE, P/FCF, and P/B ratios.")
    key_signals_summary: str = Field(description="One-sentence summary of the most critical signals observed (e.g., Graham Net-Net, high volume).")
```

---

## Step 2: Create the Agent Class

Next, create the `DailySignalsAgent` class itself. This class will orchestrate data retrieval, prompt construction, and the LLM call.

**File:** `analyst/application/agents/daily_signals.py`

```python
from pathlib import Path
from analyst.application.agents.base import Agent, AgentOutput
from analyst.application.agents.context import AgentContext

# (Add DailySignalsOutput from Step 1 here)

_PROMPT_PATH = Path(__file__).parent / "prompts" / "daily_signals.md"

class DailySignalsAgent(Agent[DailySignalsOutput]):
    """
    Agent responsible for analyzing daily market signals.
    """

    name = "DailySignals"
    output_model = DailySignalsOutput

    def __init__(self) -> None:
        self.system_prompt = _PROMPT_PATH.read_text(encoding="utf-8")

    async def run(self, ctx: AgentContext) -> AgentOutput[DailySignalsOutput]:
        # This will be implemented in the next steps
        pass
```

---

## Step 3: Create the Agent's System Prompt

Create the Markdown prompt file that will guide the LLM's analysis. This prompt will define its persona and tell it how to interpret the data.

**File:** `analyst/application/agents/prompts/daily_signals.md`

```markdown
You are a quantitative analyst specializing in technical and factor-based analysis. Your task is to analyze the provided daily market signals for a given stock and identify key trends and signals.

The data provided is a time-series from the `v_daily_market_signals` view, containing both technical indicators and point-in-time fundamental ratios.

**Data:**
{{ daily_signals_30_day }}

**Analysis Instructions:**
1.  **Momentum Analysis:**
    -   Analyze the `pct_from_50d_ma` and `pct_from_200d_ma` to determine the current price trend and its strength.
    -   Look at `volume_velocity` to identify any unusual trading activity or conviction behind price movements.
2.  **Valuation Analysis:**
    -   Review the `pe_ratio`, `price_to_fcf`, and `price_to_book` to assess the stock's current valuation relative to its own recent history.
3.  **Key Signals Summary:**
    -   Identify and summarize any standout signals. Pay special attention to `is_graham_net_net` if it is `1`, as this is a highly significant deep-value indicator.
    -   Conclude with a single, concise sentence summarizing the most critical takeaway from the data.

Produce the analysis in the requested JSON format.
```

---

## Step 4: Implement the Data Retrieval Logic

The agent needs a tool to fetch data from the `v_daily_market_signals` view. This involves creating a new repository method and a corresponding tool function that the agent can call.

### 4.1. Update the Repository
Add a new method to `analyst/infrastructure/repositories/daily_market_signals.py` to fetch the last 30 days of data.

```python
# In DailyMarketSignalsRepository class

async def get_last_30_days(self, ticker: str) -> list[DailyMarketSignalDB]:
    """Fetches the last 30 days of market signals for a ticker."""
    stmt = (
        select(DailyMarketSignalDB)
        .where(DailyMarketSignalDB.ticker == ticker)
        .where(DailyMarketSignalDB.trade_date >= date.today() - timedelta(days=30))
        .order_by(DailyMarketSignalDB.trade_date.asc())
    )
    result = await self._session.exec(stmt)
    return result.all()
```

### 4.2. Create a Tool Function
In `analyst/application/agents/tools.py`, add a new method that calls the repository and formats the data as a Markdown table for the LLM.

```python
# In AgentTools class

def get_daily_market_signals(self, ticker: str) -> str:
    """Retrieves the last 30 days of market signals and formats them as Markdown."""
    # NOTE: This would need to be async or run in a sync-to-async wrapper
    # depending on your execution model.
    signals = self.daily_market_signals_repo.get_last_30_days(ticker)
    
    if not signals:
        return "No daily market signals found for the last 30 days."

    # Convert list of Pydantic models to a Markdown table
    headers = signals[0].model_fields.keys()
    rows = [list(s.model_dump().values()) for s in signals]
    
    return self._format_as_markdown_table(headers, rows)
```

---

## Step 5: Complete the Agent's `run` Method

With the tool in place, you can now complete the agent's `run` method to orchestrate the data fetching, prompt formatting, and LLM call.

**File:** `analyst/application/agents/daily_signals.py`

```python
# In DailySignalsAgent class

async def run(self, ctx: AgentContext) -> AgentOutput[DailySignalsOutput]:
    daily_signals_md = ctx.tools.get_daily_market_signals(ctx.ticker)

    prompt = self.system_prompt.replace("{{ daily_signals_30_day }}", daily_signals_md)

    messages = [
        {"role": "system", "content": prompt},
        {"role": "user", "content": f"Analyze the daily market signals for {ctx.ticker} as of {ctx.as_of}."},
    ]

    response = await ctx.llm.complete(
        messages=messages,
        model="gemini-2.5-flash-lite", # Or your preferred model
        max_tokens=1024,
        temperature=0.2,
        response_format=self.output_model,
    )

    result = self.output_model.model_validate_json(response.text)
    total_tokens = response.input_tokens + response.output_tokens
    
    return AgentOutput(result=result, tokens=total_tokens)
```

---

## Step 6: Integrate the Agent into the Main Workflow

Finally, add the new `DailySignalsAgent` to the list of specialist agents that are run before the `SynthesizerAgent`. This is likely in your main application entry point or orchestration logic.

The `SynthesizerAgent` will then automatically receive the `DailySignalsOutput` under the key `"DailySignals"` in its `prior_outputs` context, allowing it to incorporate these insights into the final report.

This completes the end-to-end implementation.
```