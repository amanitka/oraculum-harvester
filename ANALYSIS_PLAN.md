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

- News feed ingestion.
- Automated (non-manual) analysis triggers.
- Cross-ticker peer / sector comparable analysis (requires a curated
  peer universe). Per-ticker history comparisons are in scope because
  `v_derived_metrics` already provides them.

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
- **Derived metrics access**: agents consume derived ratios on demand from
  the existing PostgreSQL view `v_derived_metrics` via the read-only
  `DerivedMetricsRepository`. No new persistence, no recomputation in
  Python — the SQL view is the single source of truth for ratios.
- **Read-only data tools**: analysis tools wrap existing analyst
  repositories (`TickerRepository`, `IncomeStatementRepository`,
  `BalanceSheetRepository`, `CashFlowStatementRepository`,
  `SharePriceRepository`, `DerivedMetricsRepository`). Agents never open
  sessions or write rows.
- **Statement template is auto-resolved, not user-chosen**: the
  `PlannerAgent` reads `Ticker.industry_name` / `Ticker.sector_name`
  and maps it to a single `StatementTemplate`
  (`general | banks | insurance`) for the whole run. Mixing templates
  inside one analysis is forbidden because the underlying SimFin
  schemas are not comparable. The resolved template is recorded in
  `payload.context.template` for traceability.
- **Statement variant is purpose-driven, not global**: each agent picks
  the `StatementVariant` (`annual | quarterly | ttm`) that matches its
  question. Fundamentals uses `annual` for multi-year trends,
  Valuation uses `ttm` for current multiples, Risk uses `quarterly`
  for volatility and earnings-quality signals. The request carries a
  `default_variant` only for the synthesizer summary table.

---

## Phase 0 — Skeleton and contracts

- Add `kafka.topics.analystRequest` to `config.yaml` and expose it via
  `_KafkaTopicsConfig` in `common/config.py`.
- Add `common/requests/analyze_ticker.py`:
  - `request_type: Literal["analyze_ticker"]`.
  - `ticker: str`, `market: str = "us"`, `as_of: date | None = None`.
  - `default_variant: StatementVariant = "annual"` — fallback when an
    agent does not specify a variant; reuses the existing
    `StatementVariant` literal from `common/domain/*`.
  - **No `template` field** — template is resolved from the ticker's
    industry inside the workflow (see Architectural decisions).
- Acceptance: `AnalyzeTickerRequest` importable, topic resolvable.

---

## Phase 1 — Sample data load

Goal: a reproducible development dataset so the analyst has data to read.

- Curate a ~20 ticker US universe (final list to be confirmed).
- Reuse `scripts/load_share_prices_initial.py` for share prices.
- Add a small bootstrap script that publishes ticker + statement fetch
  requests for the universe using existing request models.
- Document under a new README section "Bootstrap sample data".
- Universe should include **at least one banks** ticker (e.g., JPM) and
  **one insurance** ticker (e.g., MET) so all three templates exercise
  the workflow, plus general-template names.
- Acceptance: all five analyst subscribers persist rows for the universe
  and `SELECT template, variant, COUNT(*) FROM v_derived_metrics GROUP BY 1, 2`
  shows non-zero counts for every (template, variant) pair that the
  universe actually covers (e.g., general/annual, general/quarterly,
  general/ttm, banks/annual, insurance/annual).

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
  - Guaranteed Structured Outputs via LLM API (e.g. passing a JSON Schema
    via `litellm`'s `response_format`). This natively enforces the Pydantic
    model shape and eliminates the need for manual parsing retries.
- `analyst/application/agents/context.py` defines `AgentContext`:
  `ticker`, `market`, `as_of`, **`template: StatementTemplate`**
  (resolved by the planner once),
  **`default_variant: StatementVariant`**, typed read-only data tools,
  prior agent outputs by name, `LlmClient`, `token_budget`. The
  `template` field is immutable for the duration of the run.
- `analyst/application/agents/tools.py` — read-only callables into
  repositories for **Proactive Context Injection**. No explicit LLM tool
  calling is used. The orchestrator calls these functions, formats the
  returned data into efficient Markdown tables (passing the full available history), and injects it directly
  into the agent's prompt.
  No side effects, no writes, no Kafka publishes. All statement and derived
  tools accept `template: StatementTemplate` and `variant: StatementVariant`.
  The tools are:

  - `get_ticker_profile(ticker)` — `TickerRepository`. Returns the row
    used to derive the template; tools that need template do not call
    this directly.
  - `resolve_template(ticker)` — helper used by the planner; maps
    `Ticker.industry_name` / `sector_name` to one of
    `general | banks | insurance`. Falls back to `general` with a
    warning when the mapping is ambiguous.
  - `get_income_statement_history(ticker, *, template, variant, limit)`
    — `IncomeStatementRepository`.
  - `get_balance_sheet_history(ticker, *, template, variant, limit)`
    — `BalanceSheetRepository`.
  - `get_cash_flow_history(ticker, *, template, variant, limit)` —
    `CashFlowStatementRepository`.
  - `get_price_window(ticker, start, end)` — `SharePriceRepository`
    (template / variant agnostic).
  - `get_derived_metrics(ticker, *, template, variant, limit)` —
    `DerivedMetricsRepository`, returns `DerivedMetricsDB` rows from
    `v_derived_metrics` (`ebitda`, `free_cash_flow`, `ncav`,
    `net_net_working_capital`, `return_on_capital_employed`, `return_on_equity`,
    `return_on_assets`, `net_margin`, `current_ratio`, `debt_to_equity`,
    `inventory_turnover`, `asset_turnover`, `earnings_per_share`,
    `fcf_per_share`, `revenue`, `net_income`).

Template-specific note: the SimFin `banks` and `insurance` schemas
omit some columns the `general` formulas rely on, so a subset of
derived metrics will be `NULL` for those templates (e.g.,
`free_cash_flow` for banks). Agents must treat missing values as
"not applicable" rather than failing the run.

### Data inputs available to agents

| Agent        | Primary repositories                                                                                                                          |
|--------------|-----------------------------------------------------------------------------------------------------------------------------------------------|
| Planner      | `TickerRepository` (sanity check ticker exists)                                                                                               |
| Fundamentals | `IncomeStatementRepository`, `BalanceSheetRepository`, `DerivedMetricsRepository` (`return_on_capital_employed`, `return_on_equity`, `return_on_assets`, `net_margin`, `asset_turnover`, `revenue`, `net_income`) |
| CashFlow     | `CashFlowStatementRepository`, `DerivedMetricsRepository` (`free_cash_flow`, `ebitda`, `fcf_per_share`)                                       |
| Valuation    | `DerivedMetricsRepository` (`ebitda`, `free_cash_flow`, `net_income`, `shares_stabilized`, `earnings_per_share`, `fcf_per_share`), `SharePriceRepository` |
| Risk         | `BalanceSheetRepository`, `DerivedMetricsRepository` (`ncav`, `net_net_working_capital`, `current_ratio`, `debt_to_equity`, `inventory_turnover`), `SharePriceRepository` (volatility)                 |
| Synthesizer  | (no new I/O; merges prior agent outputs)                                                                                                      |

---

## Phase 7 — Agent team and orchestrator

Proposed roster (all go through the same `LlmClient`, each with its own
curated prompt in `analyst/application/agents/prompts/*.md`):

1. **PlannerAgent** — consumes the request, **resolves the statement
   template** from `Ticker.industry_name` / `sector_name`, decides
   which specialists to invoke and which (template, variant) pairs
   each one should query, and emits a plan object containing the
   frozen `template` plus per-agent variant choices.
2. **FundamentalsAgent** — interprets income statement and balance
   sheet trends. Default variant: `annual` (smooths seasonality,
   multi-year trend visibility). Reads `revenue`, `net_income`,
   `net_margin`, `return_on_capital_employed`, `return_on_assets`,
   `asset_turnover`, and `return_on_equity` history from
   `v_derived_metrics` instead of recomputing in Python.
3. **CashFlowAgent** — cash generation quality, capex intensity, and
   working-capital hygiene. Default variant: `annual`, with a
   `quarterly` cross-check for working-capital swings. Reads
   `free_cash_flow`, `fcf_per_share`, and `ebitda` from `v_derived_metrics` and joins
   with cash-flow statement details for commentary. For `banks` /
   `insurance` templates, FCF is often `NULL` and the agent must say
   so explicitly instead of fabricating values.
4. **ValuationAgent** — multiples versus the ticker's own history.
   Default variant: `ttm` (most current snapshot). Computes trailing
   P/E from `earnings_per_share` (or `net_income` and `shares_stabilized`) vs prices, EV/EBITDA
   approximation from `ebitda`, FCF yield from `fcf_per_share` (or `free_cash_flow`). For
   `banks` / `insurance` falls back to template-appropriate ratios
   (P/B from balance-sheet equity, ROE history) instead of EV/EBITDA.
   Cross-ticker peer comps remain out of scope.
5. **RiskAgent** — leverage, liquidity, earnings volatility, red flags.
   Default variant: `quarterly` (more observations for volatility).
   Uses `ncav`, `net_net_working_capital`, `current_ratio`, `debt_to_equity`,
   and `inventory_turnover` from `v_derived_metrics`
   as downside-floor sanity checks alongside balance-sheet leverage
   ratios derived from raw rows. NCAV / NNWC are only meaningful for
   the `general` template; the agent skips them for banks / insurance
   and substitutes solvency-style metrics.
6. **SynthesizerAgent** — merges all specialist outputs into the final
   markdown report and structured verdict (`verdict`, `conviction`,
   `key_drivers`, `key_risks`). Includes a header line stating the
   resolved `template` and which variants each specialist used, so a
   reader can audit the analysis lens at a glance.

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
  (news feeds, automated triggers, cross-ticker peer comps) mentioned
  off-plan.

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
    # already merged: models/derived_metrics.py
    # already merged: repositories/derived_metrics.py (reads v_derived_metrics)
alembic/versions/<rev>_add_t_analysis.py
ui/
  application/analysis_trigger.py
  infrastructure/repositories/analysis.py
  (new Analysis tab inside ui/ui.py)
docs/
  analysis_workflow.md
```

---

## Open questions (Resolved)

- **Initial ticker universe**: Start with a focused, diverse set of ~15 well-known tickers covering all templates:
  - General: AAPL, MSFT, AMZN, WMT, XOM, JNJ
  - Banks: JPM, BAC, C, WFC, GS
  - Insurance: MET, PRU, TRV, AIG
- **Default model**: Differentiate by agent load, optimizing for Google API's generous free tier ($10/mo):
  - Fast/Cheap (`gemini-2.5-flash-lite` or `gemini-2.5-flash`) for Specialists & Planner.
  - Heavyweight (`gemini-2.5-pro`) for the Synthesizer.
- **Concurrency**: Start sequential as specified. Parallelizing specialists can be evaluated after Phase 9 via `asyncio.gather()` since they share no state.
- **Industry-to-template mapping**: Create a static configuration file (e.g., `common/domain/templates.yaml`) mapping standard SimFin `industry_name` / `sector_name` to explicit templates, rather than hardcoding string matching logic in code.
- **Variant override at request time**: Keep it implicit. Specialists are prompted for specific variants; allowing the UI to override could break the prompts and lead to hallucinations.