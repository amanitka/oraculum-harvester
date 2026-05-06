## SimFin Load Transfer Redesign (Parquet + Shared Folder + Kafka Notification)

### Does this architecture make sense?

Yes — this is a strong and practical design for your current goals.

- Keep PostgreSQL as the system of record for serving and constraints.
- Move heavy data payload transfer to shared Parquet files.
- Use Kafka only as a control-plane notification (`file_ready`) to trigger ingestion.

This usually improves load performance while preserving PostgreSQL semantics.

---

### 1. Target flow (high-level)

1. Harvester fetches SimFin data and validates each record with Pydantic domain models.
2. Harvester writes standardized Parquet files to a shared folder (atomic publish).
3. Harvester emits a small Kafka `file_ready` event with metadata only.
4. Analyst consumes the event, validates file metadata and schema version.
5. Analyst bulk-loads Parquet into a staging table.
6. Analyst executes `MERGE` into target PostgreSQL table using natural keys.
7. Analyst writes ingestion run log (success/failure, row counts, checksum, timing).

---

### 2. Shared folder standard

Use a deterministic path convention:

-
`\\shared\\simfin\\{dataset}\\template={template}\\variant={variant}\\year={fiscal_year}\\run_id={run_id}\\part-000.parquet`

Rules:

- Write to `*.tmp` first, then atomic rename to final `.parquet`.
- Include `extracted_at` as non-null in every persisted record.
- Keep schema stable and versioned (`schema_version` in file metadata and Kafka event).
- Target medium file sizes (avoid many tiny files).

---

### 3. Kafka event contract (`file_ready`)

Minimal recommended payload:

- `event_type`: `simfin.file_ready`
- `dataset`: `ticker | share_price | balance_sheet | income_statement | cash_flow_statement`
- `path`: shared folder path (or URI)
- `template`: `general | banks | insurance` (for statement datasets)
- `variant`: `annual | quarterly | ttm` (for statement datasets)
- `schema_version`: integer/string
- `run_id`: unique ingestion batch identifier
- `file_checksum`: sha256
- `record_count`: integer
- `created_at`: UTC timestamp

Idempotency key on analyst side: `dataset + run_id + file_checksum`.

---

### 4. Analyst load algorithm (idempotent)

1. Receive `file_ready` event.
2. Validate required fields and supported `schema_version`.
3. Check if `dataset + run_id + file_checksum` already processed.
    - If yes: acknowledge and skip.
4. Verify file exists and checksum matches.
5. Bulk load file into `stg_<dataset>` staging table.
6. Run quality checks in staging:
    - natural-key uniqueness,
    - non-null required fields,
    - enum/domain validation,
    - `extracted_at` not null.
7. `MERGE` from staging into `t_<dataset>` target table.
8. Record run log (`loaded_rows`, `merged_rows`, duration, status, error if any).
9. Commit and acknowledge event.

Retry rules:

- Safe to retry because processing is idempotent.
- Never acknowledge before DB commit.

---

### 5. Table-by-table implementation steps

#### 5.1 `t_ticker`

1. Define ticker Parquet schema from `common.domain.ticker`.
2. Publish ticker file to shared folder with checksum.
3. Create/maintain `stg_ticker`.
4. Merge key: business identifier from ticker model (typically ticker symbol / SimFin ID).
5. Upsert descriptive fields and `extracted_at`.

#### 5.2 `t_share_price`

1. Define share-price Parquet schema from `common.domain.share_price`.
2. Partition by date (or year) to keep files balanced.
3. Create/maintain `stg_share_price`.
4. Merge key: `ticker + date` (or current primary key definition).
5. Upsert OHLCV and related fields, preserve `extracted_at`.

#### 5.3 `t_balance_sheet`

1. Use `common.domain.balance_sheet.BalanceSheet` for normalization.
2. Ensure `template` and `variant` are always present.
3. Create/maintain `stg_balance_sheet`.
4. Merge key: `ticker + fiscal_year + fiscal_period + template + variant`.
5. Upsert all statement fields and `extracted_at`.

#### 5.4 `t_income_statement`

1. Use `common.domain.income_statement` model as source schema.
2. Keep consistent handling of `template`, `variant`, and date fields.
3. Create/maintain `stg_income_statement`.
4. Merge key: `ticker + fiscal_year + fiscal_period + template + variant`.
5. Upsert all statement fields and `extracted_at`.

#### 5.5 `t_cash_flow_statement`

1. Use `common.domain.cash_flow_statement` model as source schema.
2. Keep same partitioning and naming policy as other statements.
3. Create/maintain `stg_cash_flow_statement`.
4. Merge key: `ticker + fiscal_year + fiscal_period + template + variant`.
5. Upsert all statement fields and `extracted_at`.

---

### 6. Rollout plan (safe migration)

1. Implement Parquet writer + event publisher in Harvester (without removing current path).
2. Implement staging + merge + run log in Analyst.
3. Run dual mode in non-prod and compare counts/checksums vs current ingestion.
4. Enable table-by-table cutover in this order:
    - `t_ticker`
    - `t_share_price`
    - `t_balance_sheet`
    - `t_income_statement`
    - `t_cash_flow_statement`
5. Monitor load times, duplicate rate, failed runs.
6. Disable old payload-heavy path after stable period.

---

### 7. Acceptance checklist

- No duplicate rows after repeated same event.
- `extracted_at` always non-null in all target tables.
- Kafka messages remain small (metadata only).
- Throughput improved versus direct row-by-row ingestion.
- Full replay of one historical run succeeds without manual cleanup.
