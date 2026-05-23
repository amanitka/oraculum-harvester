# AGENTS.md

Operating manual for AI coding agents (and humans) working on this Python
enterprise codebase. These rules are **normative**: if something conflicts
with them, raise it instead of silently deviating.

---

## 1. Mission & scope

- Deliver **production-grade** Python: correct, readable, testable, observable, secure.
- Prefer **small, reversible, minimal** changes over large rewrites.
- Always identify the **root cause** before patching a symptom.
- Never weaken or delete tests without explicit human approval.

---

## 2. Project layout

Follow a **layered / hexagonal** structure. Each service lives in its own
top-level package; shared code lives in `common/`.

```
<service>/
    __init__.py
    <service>.py          # thin orchestrator / entry point
    providers/            # strategy implementations (vendor adapters)
        base.py           # ABC contract
        <vendor>.py       # one file per vendor
    application/          # use-cases / business logic (pure, no I/O)
    infrastructure/       # adapters (db, http, kafka, files)

common/
    domain/               # Pydantic models, enums, value objects
    messaging/            # shared producer/consumer providers
    config.py             # typed config accessor (single source of truth)
```

Rules:

- **No cyclic imports.** `domain` never imports from `application`/`infrastructure`.
- **No vendor SDK in orchestrators.** Keep `simfin`, `boto3`, `psycopg`, etc. inside adapters.
- **One class per responsibility.** If a file exceeds ~200 lines, consider splitting.
- **Database objects naming.** Use standard prefixes consistently: `t_` tables (`t_ticker`), `v_` views (`v_latest_ticker`), `pk_` primary keys, `fk_` foreign keys, `uq_` unique constraints, `ix_` indexes, `ck_` check constraints.
- **Extraction timestamp.** Persisted market-data entities must include a non-null `extracted_at` timestamp representing when harvester fetched the source dataset.

---

## 3. Python language & tooling

- **Python version**: honor `pyproject.toml` `requires-python`. Do not use syntax/features older than that baseline.
- **Package manager**: `uv` (`uv.lock` is committed). Add deps via `uv add <pkg>`, never hand-edit `uv.lock`.
- **Formatting / linting**: `ruff format` + `ruff check --fix`. Line length 100. No other formatters.
- **Typing**: `mypy --strict` on `common/` and all new code. Public APIs must be fully annotated.
- **Imports**: absolute only; grouped stdlib / third-party / first-party, alphabetized within groups.

---

## 4. Clean-code rules (hard limits)

- **Function length**: aim for ≤ 20 lines of body, hard cap 40. Extract helpers rather than nest.
- **Cyclomatic complexity**: ≤ 8. Prefer early returns over nested `if/else`.
- **Parameters**: ≤ 5 positional; beyond that use a dataclass / Pydantic model.
- **Naming**: descriptive, no abbreviations (`industry_map`, not `ind_map`). Boolean variables read as predicates (`is_valid`, `has_cik`).
- **Comments**: explain **why**, never **what**. Delete dead code; do not comment it out.
- **Docstrings**: mandatory on every public module, class, and function. One-line summary + optional body. Use imperative mood.
- **No magic values**: extract to module-level constants with `UPPER_SNAKE_CASE`.
- **Side effects at import time are forbidden** except: logger creation, constant definition, decorators.

---

## 5. Architecture patterns

### Dependency injection
- Inject collaborators via the constructor. **Never** reach for globals inside classes.
- Use **abstract base classes** (`abc.ABC`) for extension points (providers, repositories, gateways). Concrete implementations live in sibling modules and are chosen at the composition root (`main()`).

### Singletons
- A naive GoF singleton (`__new__` / metaclass) is an **anti-pattern**—it breaks tests.
- Acceptable alternatives, in order of preference:
  1. **Lazy provider class** with `get()` / `reset()` + `atexit` hook (see `common/messaging/producer.py`).
  2. `@functools.lru_cache(maxsize=1)` factory — only when no lifecycle management is needed.
  3. Module-level instance — only for stateless, cheap-to-create objects.
- Resources that own connections (Kafka, DB pools, HTTP clients) belong in option 1.

### Data boundaries
- Validate **once** at the edge with Pydantic (`Model.model_validate`). Inside the domain, trust the types.
- Serialize with `model_dump(mode="json")` so `datetime`/`Decimal`/`UUID` are JSON-safe.
- Use `Iterator[T]` / generators for streaming large datasets; avoid materializing full lists.

---

## 6. Configuration

- All config goes through `common.config.config` (a typed facade over YAML + env).
- **Never** read `os.environ` or open files outside that module.
- Secrets come from environment variables only. Never commit `.env`, keys, or tokens.
- Every config key must have: a default (safe for local dev) **or** a clear failure message if missing.

---

## 7. Logging & observability

- Use the stdlib `logging` module. `logger = logging.getLogger(__name__)` at module top.
- **Never `print()`** in library or service code. `print` is allowed only in one-off CLI scripts under `scripts/`.
- Log levels: `DEBUG` dev-only detail · `INFO` lifecycle milestones · `WARNING` recoverable anomalies · `ERROR` failed operations · `CRITICAL` process-terminating.
- Prefer **structured log args** (`logger.info("published %d", n)`) over f-strings so formatting is lazy.
- Include correlation/trace IDs in long-running pipelines.

---

## 8. Error handling

- **Never** write bare `except:` or `except Exception: pass`. Always log or re-raise with context.
- Catch the **narrowest** exception that is actually thrown.
- Wrap vendor errors in domain exceptions at adapter boundaries so callers aren't coupled to SDKs.
- Fail fast on programmer errors (asserts, `raise ValueError`); retry only idempotent I/O failures.

---

## 9. Concurrency

- Prefer `asyncio` for I/O-bound work, process pools for CPU-bound work. Don't mix threads and asyncio casually.
- Shared mutable state requires a `threading.Lock` (or `asyncio.Lock`). Document the invariant it protects.
- Kafka producers and most HTTP clients are thread-safe and **must be shared** per process — do not instantiate per call.

---

## 10. Testing

- Framework: `pytest` + `pytest-asyncio`. Coverage target: **≥ 85%** on new code.
- Mirror source layout under `tests/` (`harvester/providers/simfin.py` → `tests/harvester/providers/test_simfin.py`).
- Every bug fix ships with a **regression test** that fails before the fix.
- Use fakes/stubs over mocks when possible; mock only at adapter boundaries.
- `pytest -q` must pass locally before requesting review.

---

## 11. Security

- Never log secrets, tokens, or PII. Add a redaction filter if unsure.
- Pin dependencies via `uv.lock`. Review `uv pip audit` output before release.
- Use `pathlib.Path`, not string concatenation, for file paths.
- Parameterize SQL; never f-string user input into queries.

---

## 12. Documentation & commits

- Update `README.md` / relevant docs in the **same commit** as the code change.
- Conventional commit prefixes: `feat:`, `fix:`, `refactor:`, `perf:`, `test:`, `docs:`, `chore:`.
- One logical change per commit. Keep PRs ≤ ~400 lines of diff when feasible.
- PR description must answer: **What**, **Why**, **How verified**.

---

## 13. Platform & tooling notes (this repo)

- OS: Windows. Files are stored with **CRLF** line endings — keep them that way; `.gitattributes` should enforce it.
- Runtime: `uv run python -m <module>`; do **not** invoke the system Python.
- Don't commit: `.env`, `data/`, `__pycache__/`, `_*.py` scratch files, SimFin cache.

---

## 14. Checklist before finishing a task

- [ ] Code compiles and imports resolve (`python -m py_compile` or `uv run pytest --collect-only`).
- [ ] `ruff check` + `ruff format --check` clean.
- [ ] `mypy --strict` clean on touched packages.
- [ ] Tests added/updated and passing.
- [ ] Docstrings on new public symbols.
- [ ] No TODOs left without an owner and ticket reference.
- [ ] No new global singletons, bare excepts, or `print()` calls.
- [ ] Secrets/configs unchanged or documented.

---

## 15. Common Pitfalls & Explicit Patterns (This Repo)

This section documents specific, non-obvious patterns in this codebase that require manual "housekeeping" steps. Forgetting these steps is a common source of errors.

### 15.1. Adding New Domain Models or Requests

When adding a new Pydantic model to `common/domain` or a new request model to `common/requests`, two files must be changed:
1.  **The new module file** (e.g., `common/domain/news.py`).
2.  **The package's `__init__.py` file** (e.g., `common/domain/__init__.py`). You must import the new class and add it to the `__all__` list. This "barrel" pattern makes the class part of the package's public API.

### 15.2. Adding a New Request Type to a Topic

When adding a new request type that will be sent to the `harvester_request_topic`, two files must be changed:
1.  **The new request module** (e.g., `common/requests/fetch_news.py`).
2.  **`common/requests/__init__.py`**: The new request class must be added to the `AnyRequest` discriminated union. This is critical for FastStream to correctly deserialize messages.

### 15.3. FastStream Application Structure

- **Import Order Matters**: In `harvester/app.py` and `analyst/app.py`, the `broker` object must be created *before* any modules containing `@broker.subscriber` or `@broker.publisher` decorators are imported. This means local application imports should come after the `broker` is instantiated.
- **Circular Imports**: A `...subscriber` module cannot import the `app` module that imports it. Dependencies must flow in one direction.

### 15.4. Alembic Migrations

- **`down_revision` Must Be Exact**: When creating a new migration, the `down_revision` variable must exactly match the `revision` variable of the previous migration file (e.g., `'0006_daily_market_signals'`, not just `'0006'`).

### 15.5. Data Ingestion & Validation Patterns

- **Enrich, Then Validate**: When processing data from external APIs, do not validate against a strict Pydantic model immediately. First, perform any necessary enrichment (e.g., generating IDs, denormalizing metadata). Then, validate the *enriched* data against the final, strict model. This prevents validation errors on fields that are generated internally.
- **De-duplicate Before Batch `UPSERT`**: When preparing a batch of data for a database `INSERT ... ON CONFLICT` (UPSERT) operation, you **must** programmatically de-duplicate the data *within the batch* first. The `ON CONFLICT` clause only handles conflicts with data already in the table, not duplicates within the incoming batch itself. Failure to do this will result in a `CardinalityViolation` error.
