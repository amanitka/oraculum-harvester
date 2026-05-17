# Analysis Workflow

This document describes the multi-agent LLM-driven ticker analysis capability in Oraculum.

## Architecture

The workflow uses a deterministic, sequential multi-agent approach to analyze financial data from the local database. It is orchestrated by the `AnalysisWorkflow` class.

### Agent Roster

1.  **PlannerAgent**: Determines the correct statement template (`general`, `banks`, `insurance`) based on the ticker's industry.
2.  **FundamentalsAgent**: Analyzes revenue, margin, and ROCE trends using annual data.
3.  **CashFlowAgent**: Evaluates cash generation quality and capex intensity.
4.  **ValuationAgent**: Assesses current valuation multiples against historical averages using TTM data.
5.  **RiskAgent**: Identifies red flags in leverage and liquidity using quarterly data.
6.  **SynthesizerAgent**: Merges all specialist outputs into a final Markdown report and structured verdict.

### Prompts

Agent prompts are located in `analyst/application/agents/prompts/*.md`. They are loaded at import time. This makes the prompts reviewable like code and easy to diff. Data is injected directly into these templates by the orchestrator.

### Configuration

LLM configurations are managed in `config.yaml` under the `llm` block:

```yaml
llm:
  provider: groq
  model: llama-3.3-70b-versatile
  maxTokens: 4096
  temperature: 0.2
  workflowTokenBudget: 100000
```

API keys must be provided as environment variables (`GROQ_API_KEY`, `OPENAI_API_KEY`, `GEMINI_API_KEY`).

### UI Integration

The analysis is triggered by publishing an `AnalyzeTickerRequest` to Kafka. The UI reads the results directly from the `t_analysis` PostgreSQL table.
