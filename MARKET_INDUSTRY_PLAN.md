# Markets and Industries Implementation Plan

Roadmap for ingesting and persisting static SimFin metadata (Markets and Industries) into Oraculum. This follows the exact same event-driven pattern as Tickers.

---

## Goal
Enable the pipeline to fetch Market and Industry definitions from SimFin, publish them to Kafka, and persist them into the PostgreSQL database. This provides a robust foundation for explicit template mapping, UI filtering, and future peer-comparison features.

---

## Phase 0 — Domain Models and Contracts

- **Domain Models**: Create `common/domain/market.py` and `common/domain/industry.py` defining Pydantic models for `Market` and `Industry`.
  - `Industry` fields: `industry_id` (PK), `sector_name`, `industry_name`.
  - `Market` fields: `market_id` (PK), `market_name`, `currency`.
- **Request Models**: Create `common/requests/fetch_market.py` and `common/requests/fetch_industry.py`.
  - Similar to `FetchTickerRequest`, but no need for parameters since SimFin returns the global list.

---

## Phase 1 — Kafka Configuration

- **Topics**: Add `market: oraculum.market` and `industry: oraculum.industry` to `config.yaml` under `kafka.topics`.
- **Config Accessor**: Update `_KafkaTopicsConfig` in `common/config.py` to expose these new topics.

---

## Phase 2 — Database Models and Migrations

- **SQLModels**: Create `analyst/infrastructure/models/market.py` (`t_market`) and `analyst/infrastructure/models/industry.py` (`t_industry`).
  - Add explicit mapping logic to the Industry model: a `statement_template` column (`Literal["general", "banks", "insurance"]`) that can be derived during upsert or manually maintained.
- **Alembic**: Generate an Alembic migration to create `t_market` and `t_industry` tables.
- **Repositories**: Create `MarketRepository` and `IndustryRepository` in `analyst/infrastructure/repositories/` with `upsert_batch` methods.

---

## Phase 3 — Harvester (Producer)

- **SimFin Provider**: Create `harvester/providers/market.py` and `harvester/providers/industry.py`.
  - Use SimFin's `load_markets()` and `load_industries()` respectively.
  - Map the Pandas DataFrames to the domain Pydantic models.
- **Subscribers**: Create `harvester/subscribers/fetch_market.py` and `harvester/subscribers/fetch_industry.py`.
  - Consume `FetchMarketRequest` / `FetchIndustryRequest` from the harvester request topic.
  - Fetch data via the provider.
  - Publish domain models to `oraculum.market` / `oraculum.industry` topics.

---

## Phase 4 — Analyst (Consumer)

- **Subscribers**: Create `analyst/subscribers/market.py` and `analyst/subscribers/industry.py`.
  - Consume from `oraculum.market` / `oraculum.industry`.
  - Parse payloads into domain models.
  - Use `MarketRepository` / `IndustryRepository` to bulk upsert into PostgreSQL.

---

## Phase 5 — UI & Integration

- **UI Factory**: Update `ui/application/refresh_request_factory.py` to include `build_market_request` and `build_industry_request`.
- **Streamlit App**: Add forms to `ui/app.py` under the "Refresh" tab to allow manual triggering of Market and Industry ingestion.
- **Data Tools Refactor**: Update `AgentDataTools.resolve_template` to fetch the template directly from the `t_industry` database table instead of using hardcoded string matching.