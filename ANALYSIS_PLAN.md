# Analysis Workflow — Development Plan

Roadmap for adding the LLM-driven ticker analysis capability to Oraculum.
This document is the single source of truth for the feature; each phase is
designed to be small, reversible, and independently verifiable per
`AGENTS.md`.

---

## Goal

Enable a user to trigger an analysis of a specific ticker from the UI.
The analyst service pulls the relevant data from PostgreSQL, runs a
multi-agent LLM workflow, persists the result, and the UI displays it so
the user can review and act on it.

Out of scope for this plan (explicitly deferred):

- Derived SimFin metrics.
- News feed ingestion.
- Automated (non-manual) analysis triggers.

---

## Architectural decisions

- **Command path UI -> analyst**: Kafka, new topic `oraculum.analyst.request`.
  Keeps uniform messaging pattern with the existing harvester flow.
- **Result path analyst -> UI**: database only. UI reads directly from
  PostgreSQL with a short polling auto-refresh. No websockets, no
  completion topic (can be added later for automation triggers).
- **Co-location**: analyst and UI run as a single pod, sharing the same DB.
- **LLM abstraction**: single provider-agnostic adapter using **LiteLLM**,
  isolated behind an `LlmClient` ABC so the rest of the code never imports
  `litellm` directly.
- **Provider flexibility**: Groq, Gemini, and OpenAI selectable via
  configuration only, no code change. API keys via environment variables.
- **Agent framework**: hand-rolled, minimal, deterministic orchestration.
  No LangChain / CrewAI / AutoGen. Each agent is a Pydantic-typed class
  with a curated prompt loaded from a `.md` file.
- **Domain boundary**: analysis domain lives in `analyst/` (analyst
  concern). Only `AnalyzeTickerRequest` goes in `common/requests/` because
  it is a cross-service contract (UI publishes, analyst consumes).
- **Correlation**: the `correlation_id` from `AnalyzeTickerRequest` is
  reused as the primary key of the persisted analysis row. One trace id
  from UI submit through Kafka through DB record.

---

## Phase 0 — Skeleton and contracts

- Add `kafka.topics.analystRequest` to `config.yaml` and expose it via
  `_KafkaTopicsConfig` in `common/config.py`.
- Add `common/requests/analyze_ticker.py`:
  - `request_type: Literal["analyze_ticker"]`
  - `ticker: str`, `market: str = "us"`, `as_of: date | None = None`.
- Acceptance: `AnalyzeTickerRequest` importable, topic resolvable.

---

## Phase 1 — Sample data load

Goal: a reproducible development dataset so the analyst has data to read.

- Curate a ~20 ticker US universe (final list to be confirmed).
- Reuse `scripts/load_share_prices_initial.py` for share prices.
- Add a small bootstrap script that publishes ticker + statement fetch
  requests for the universe using existing request models.
- Document under a new README section "Bootstrap sample data".
- Acceptance: all five analyst subscribers persist rows for the universe.

---

## Phase 2 — Analysis storage

- New domain model under `analyst/application/analysis/models.py`:
  - `AnalysisStatus = Literal["pending", "running", "completed", "failed"]`
  - `AnalysisResult` (Pydantic) with fields: `ticker`, `market`, `as_of`,
    `status`, `report_md`, `verdict` (`bull|bear|neutral`),
    `conviction` (1..5), `key_drivers`, `key_risks`, `agent_trace`,
    `token_usage`, `error`, `created_at`, `updated_at`.
- New SQLModel `AnalysisDB` -> table `t_analysis`:
  - PK `correlation_id UUID`.
  - Columns: `ticker`, `market`, `as_of`, `status`, `report_md`,
    `verdict`, `conviction`, `payload JSONB` (full structured result +
    per-agent traces), `error`, `created_at`, `updated_at`.
  - Indexes: `ix_analysis_ticker_market_created`,
    `ix_analysis_status_created`.
- Alembic migration.
- `AnalysisRepository` with `insert_pending`, `mark_running`,
  `mark_completed`, `mark_failed`, `get_by_id`, `list_recent`,
  `list_by_ticker`.
- Acceptance: repository-level tests pass.

---

## Phase 3 — Analyst command path (stub workflow)

- New subscriber `analyst/subscribers/analyze_ticker.py`:
  - Consumes `config.topics.analyst_request`.
  - Lifecycle: `insert_pending` -> `mark_running` -> run workflow ->
    `mark_completed` / `mark_failed`.
- Stubbed `run_workflow()` returns a fixed markdown string. This proves
  end-to-end wiring before introducing LLM calls.
- Acceptance: publishing an `AnalyzeTickerRequest` from a CLI helper
  results in a `t_analysis` row progressing through all statuses.

---

## Phase 4 — UI: trigger and view

- New top-level `Analysis` tab in `ui/ui.py` with two sub-tabs:
  - **Run analysis**: form with ticker + market, publishes
    `AnalyzeTickerRequest`. Displays `correlation_id` on submit.
  - **Analyses**: paginated list from `t_analysis` (ticker, status,
    created_at, verdict). Auto-refresh every ~3s while any row is
    `pending` or `running`. Clicking a row opens a detail view that
    renders the markdown report plus the structured verdict block.
- Generalize `KafkaRefreshRequestPublisher` into a
  `KafkaRequestPublisher` (topic resolved per `request_type`) so the UI
  has one publishing adapter.
- New read-only `ui/infrastructure/repositories/analysis.py` that the UI
  consumes directly (co-located, same DB).
- Acceptance: manual trigger from UI leads to a stubbed report visible
  within seconds; status progresses live.

---

## Phase 5 — LLM provider abstraction (LiteLLM)

- `uv add litellm`.
- `common/llm/base.py`:
  - `LlmClient` ABC with
    `async complete(messages, *, model, max_tokens, temperature,
    response_format) -> LlmResponse`.
  - `LlmResponse` Pydantic: `text`, `model`, `input_tokens`,
    `output_tokens`, `latency_ms`.
- `common/llm/litellm_client.py` — single adapter around
  `litellm.acompletion`. Provider and model sourced from config.
- Config additions in `config.yaml`:

  ```yaml
  llm:
    provider: groq        # groq | openai | gemini
    model: llama-3.3-70b-versatile
    maxTokens: 4096
    temperature: 0.2
  ```

- API keys via environment only: `GROQ_API_KEY`, `OPENAI_API_KEY`,
  `GEMINI_API_KEY`. LiteLLM picks up whichever matches the chosen
  provider. Never logged.
- Retry policy: retry transient errors (network, 5xx, rate limit) with
  bounded backoff; fail fast on 4xx auth/validation errors.
- Unit tests with a fake `LlmClient`.

---

## Phase 6 — Agent framework (minimal)

- `analyst/application/agents/base.py`:
  - `class Agent(ABC)` with `name`, `system_prompt`,
    `input_model: type[BaseModel]`, `output_model: type[BaseModel]`,
    `async run(ctx: AgentContext) -> Output`.
  - JSON-mode output enforced via prompt plus Pydantic validation. On
    validation failure, one automatic retry with a "fix your JSON"
    correction message, then surface error.
- `analyst/application/agents/context.py` defines `AgentContext`:
  `ticker`, `market`, `as_of`, typed read-only data tools, prior agent
  outputs by name, `LlmClient`, `token_budget`.
- `analyst/application/agents/tools.py` — read-only callables into
  repositories: `get_latest_fundamentals`, `get_price_window`,
  `get_income_statement_history`, `get_balance_sheet_history`,
  `get_cash_flow_history`. No side effects.

---

## Phase 7 — Agent team and orchestrator

Proposed roster (all go through the same `LlmClient`, each with its own
curated prompt in `analyst/application/agents/prompts/*.md`):

1. **PlannerAgent** — consumes the request, decides which specialists
   to invoke and which data tools to call, emits a plan object.
2. **FundamentalsAgent** — interprets income statement and balance
   sheet trends (growth, margins, capital structure).
3. **CashFlowAgent** — cash generation quality, free cash flow,
   capex intensity, working-capital hygiene.
4. **ValuationAgent** — multiples versus own history (sector comps out
   of scope until derived metrics arrive).
5. **RiskAgent** — leverage, liquidity, earnings volatility, red flags.
6. **SynthesizerAgent** — merges all specialist outputs into the final
   markdown report and structured verdict (`verdict`, `conviction`,
   `key_drivers`, `key_risks`).

Deterministic `AnalysisWorkflow.run(request) -> AnalysisResult`:

- Sequential by default (simpler, reviewable traces). Parallelization of
  specialists deferred to a later iteration.
- Persists every agent output in `payload.agent_trace` for auditability.
- Enforces: hard per-run token budget, wall-clock timeout, Pydantic
  validation on every agent output, structured logs per LLM call
  (`cid`, `agent`, `input_tokens`, `output_tokens`, `latency_ms`,
  `model`).

Prompt authoring convention:

- One `.md` file per agent under `analyst/application/agents/prompts/`.
- Loaded at import time and embedded in the agent instance.
- Diff-friendly; prompts reviewed like code.

---

## Phase 8 — Wire real workflow into the analyst subscriber

- Replace the Phase 3 stub with
  `AnalysisWorkflow(LiteLlmClient(), AgentContextFactory(session))`.
- Status transition logic unchanged, so the UI requires no change.
- Acceptance: triggering an analysis from the UI produces a real report
  visible in the UI, within the token and time budgets.

---

## Phase 9 — Tests and observability

- Unit tests for every agent with a fake `LlmClient` returning canned
  JSON. Validates Pydantic output handling, retry-on-invalid-JSON.
- Integration test: publish `AnalyzeTickerRequest`, assert a
  `completed` row exists with a valid `AnalysisResult`.
- Structured logs across the pipeline:
  `cid=<correlation_id> phase=<planner|fundamentals|...> ...`.
- Log redaction filter to guarantee LLM API keys never leak.

---

## Phase 10 — Documentation and checkpoint

- New README section "Running an analysis" (how to trigger from UI,
  where reports appear).
- New `docs/analysis_workflow.md` describing the agent roster, prompt
  file locations, and configuration keys.
- Review checkpoint before proceeding to the deferred extensions
  (derived metrics, news feeds) mentioned off-plan.

---

## Target file layout

```
common/
  requests/analyze_ticker.py
  llm/base.py
  llm/litellm_client.py
analyst/
  subscribers/analyze_ticker.py
  application/
    analysis/models.py
    analysis/workflow.py
    agents/base.py
    agents/context.py
    agents/tools.py
    agents/planner.py
    agents/fundamentals.py
    agents/cash_flow.py
    agents/valuation.py
    agents/risk.py
    agents/synthesizer.py
    agents/prompts/*.md
  infrastructure/
    models/analysis.py
    repositories/analysis.py
alembic/versions/<rev>_add_t_analysis.py
ui/
  application/analysis_trigger.py
  infrastructure/repositories/analysis.py
  (new Analysis tab inside ui/ui.py)
docs/
  analysis_workflow.md
```

---

## Open questions

- **Initial ticker universe**: do you want to provide the ~20 tickers,
  or pick canonical names such as large-cap US leaders.
- **Default model**: fix a default model per provider, or leave fully
  config-driven with sensible examples only.
- **Concurrency**: start sequential as specified, then evaluate
  parallelizing specialists after Phase 9 — confirm.
