# Oraculum

Event-driven financial data pipeline built with FastStream (Kafka), SimFin,
SQLModel, and PostgreSQL.

---

## Architecture

```
FetchXxxRequest → [Kafka: oraculum.harvester.request]
    → harvester (SimFin fetch + publish)
        → [Kafka: oraculum.ticker / oraculum.share_price_batch / ...]
            → analyst (persist to PostgreSQL)
```

Two services:

- **harvester** — consumes fetch requests, pulls data from SimFin, publishes domain events.
- **analyst** — consumes domain events, persists them to PostgreSQL, and runs APScheduler jobs that publish periodic refresh requests to Kafka.

---

## Prerequisites

| Tool | Purpose |
|---|---|
| Python ≥ 3.14 | Runtime |
| `uv` | Package manager / runner |
| PostgreSQL ≥ 14 | Database |
| Kafka ≥ 3.x | Message broker |

---

## Configuration

Copy `.env.example` to `.env` and set the following variables:

```dotenv
ORACULUM_SIMFIN_API_KEY=your_simfin_key
ORACULUM_KAFKA_BROKERS=localhost:9092
ORACULUM_DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/oraculum
ORACULUM_HARVESTER_DATA_PATH=./data
```

All defaults in `config.yaml` work for local development without a `.env` file,
except `ORACULUM_SIMFIN_API_KEY` which is always required.

---

## Database setup

```powershell
# Apply all migrations (creates t_ticker, t_share_price, statement tables, etc.)
uv run alembic upgrade head
```

`t_share_price` is a PostgreSQL range-partitioned table (by `trade_date`).
Monthly partitions from **1990-01** through the current month **+9 months**
are created automatically every time the analyst service starts.

Fundamentals statement tables (`t_income_statement`, `t_balance_sheet`,
`t_cash_flow_statement`) persist a `variant` discriminator (`annual`,
`quarterly`, `ttm`) and include it in `composite_key`.

---

## Running the services

```powershell
# One command — analyst (consumer + scheduler) + Streamlit UI
uv run python scripts/run_ops_stack.py

# Or run separately:
# Terminal 1 — analyst (consumer + DB writer)
uv run python -m analyst

# Terminal 2 — harvester (producer)
uv run python -m harvester

# Terminal 3 — Streamlit operations UI
uv run streamlit run ui/ui.py
```

---

## Operations UI

The Streamlit UI currently provides an operations console with a dedicated
`Refresh` tab. Each form publishes one request message to
`oraculum.harvester.request` and shows the request `correlation_id` so runs are
traceable in logs.

Available refresh forms:

- Ticker refresh
- Share-price refresh
- Income statement refresh
- Balance sheet refresh
- Cash-flow statement refresh

The `Analysis` tab is a placeholder for upcoming analyst output views.

---

## Triggering data ingestion

Send a fetch request to the harvester request topic.  Example helper scripts
live in the repo root as `_send_fetch_*.py`.

### Tickers
```powershell
uv run python _send_fetch_ticker.py
```

### Share prices — incremental (Kafka flow)

The incremental flow sends a `FetchSharePriceRequest` to the harvester.  The
harvester loads SimFin data, filters to `trade_date >= from_date - safety_window_days`,
chunks rows into batches of 500, and publishes them to the
`oraculum.share_price_batch` topic.  The analyst consumes each batch and
bulk-upserts it into `t_share_price`.

```python
# _send_fetch_share_price.py  (create manually or adapt from _send_fetch_ticker.py)
from datetime import date
from common.requests.share_price import FetchSharePriceRequest
# publish FetchSharePriceRequest(market="us", from_date=date(2024, 1, 1))
```

### Share prices — initial bulk load (direct DB, bypasses Kafka)

For the **first-ever load** of 6 M+ historical rows use the bulk script:

```powershell
# Ensure alembic upgrade head has been run first
uv run python scripts/load_share_prices_initial.py --market us --variant daily
```

The script:
1. Loads all SimFin share price data from the local cache.
2. Creates any missing monthly partitions (1990-01 → now + 9 months).
3. COPYs rows in chunks of 50 000 into a temporary staging table.
4. Upserts from staging into `t_share_price` using `ON CONFLICT DO UPDATE`.

The analyst fundamentals refresh job publishes requests for all statement
variants (`annual`, `quarterly`, and `ttm`) per market.

Re-running is safe — all rows are idempotent on `(ticker, market, trade_date)`.

---

## Database object naming conventions

| Prefix | Object type |
|---|---|
| `t_` | Tables |
| `v_` | Views |
| `pk_` | Primary keys |
| `fk_` | Foreign keys |
| `uq_` | Unique constraints |
| `ix_` | Indexes |
| `ck_` | Check constraints |

---

## Development

```powershell
# Lint + format
uv run ruff check --fix .
uv run ruff format .

# Type-check
uv run mypy --strict common/ analyst/ harvester/

# Compile-check a file
uv run python -m py_compile path/to/file.py
```