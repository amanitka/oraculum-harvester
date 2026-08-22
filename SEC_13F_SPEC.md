# SEC 13F Institutional Holdings — Implementation Plan

## Overview

Harvesting, transporting, and storing SEC Form 13F institutional holdings data across the **Oraculum** ecosystem:

- **Harvester** (Python / FastStream): Fetches raw 13F data from SEC, transforms it, writes Parquet files, publishes Kafka events.
- **Oraculum** (Java / Spring): Orchestrates harvesting schedules, consumes Parquet files, stores data in the database, calls stored procedure for delta computation, and exposes API/UI.

**Scope**: Personal app for current-state analysis. Only 2 quarters retained in DB (current + previous). No historical backfill or backtesting.

---

## System Responsibility Split

```
┌──────────────────────────────────────────────────────────────────────────────────┐
│                         ORACULUM (Java / Spring)                                │
│                                                                                  │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────────────┐  │
│  │ Scheduler /      │   │ Kafka Consumer   │   │ Database & Analytics         │  │
│  │ REST API         │   │ (data_file_ready)│   │                              │  │
│  │                  │   │                  │   │ • Read Parquet files         │  │
│  │ • Cron: trigger  │   │ • Receive event  │   │ • Upsert into DB tables     │  │
│  │   quarterly bulk │   │ • Read parquet   │   │ • CALL sp_compute_sec_      │  │
│  │ • Poll: Tier 1   │   │ • Persist to DB  │   │   holding_delta(...)        │  │
│  │   CIK real-time  │   │ • Drop old       │   │ • Expose REST API           │  │
│  │ • Manage filer   │   │   partitions     │   │                              │  │
│  │   registry       │   │                  │   │                              │  │
│  └────────┬─────────┘   └──────────────────┘   └──────────────────────────────┘  │
│           │                                                                      │
│           │  Kafka: oraculum.harvester.request                                   │
│           ▼                                                                      │
├──────────────────────────────────────────────────────────────────────────────────┤
│                        HARVESTER (Python / FastStream)                           │
│                                                                                  │
│  ┌─────────────────┐   ┌──────────────────┐   ┌──────────────────────────────┐  │
│  │ Kafka Subscriber │   │ 13F Services     │   │ SEC Provider                 │  │
│  │                  │   │                  │   │                              │  │
│  │ • Receive request│──▶│ • Bulk Service   │──▶│ • Download SEC Bulk Zip     │  │
│  │ • Pattern match  │   │ • CIK Service    │   │ • Parse INFOTABLE.tsv       │  │
│  │ • Route to svc   │   │ • Filers Service │   │ • Download CIK submissions  │  │
│  │                  │   │                  │   │ • Parse InfoTable XML       │  │
│  └──────────────────┘   └────────┬─────────┘   └──────────────────────────────┘  │
│                                  │                                                │
│                                  ▼                                                │
│                    ┌──────────────────────────┐                                   │
│                    │ Parquet Writer            │                                   │
│                    │ • Write to exchange dir   │                                   │
│                    │ • SHA-256 checksum        │                                   │
│                    │ • Publish DataFileReady   │                                   │
│                    └──────────────────────────┘                                   │
└──────────────────────────────────────────────────────────────────────────────────┘
```

---

## Codebase Integration Points (Exact Files)

### Oraculum Harvester (Python) — Files to Create/Modify

| File | Action | Description |
|:---|:---|:---|
| `common/requests/sec_13f.py` | **NEW** | `Fetch13FBulkRequest`, `Fetch13FCikRequest`, `Fetch13FFilersRequest` Pydantic models |
| `common/requests/__init__.py` | **MODIFY** | Add 3 new types to `AnyRequest` union |
| `common/domain/sec_13f.py` | **NEW** | `Sec13FHolding`, `Sec13FFiler` Pydantic domain models |
| `common/domain/data_file_ready.py` | **MODIFY** | Add `"sec_13f_holding"`, `"sec_13f_filer"` to `DatasetType` literal |
| `harvester/services/sec_13f.py` | **NEW** | Orchestration: download → parse → write parquet → publish event |
| `harvester/providers/sec_provider.py` | **MODIFY** | Add methods: `download_13f_bulk_zip()`, `fetch_cik_submissions()`, `fetch_13f_master_index()` |
| `harvester/subscribers/request.py` | **MODIFY** | Add `match` arms for the 3 new request types |
| `common/config.py` | **MODIFY** | Add SEC config block (user-agent, rate limit, base URLs) |

### Oraculum (Java / Spring) — Files to Create/Modify

| File | Action | Description |
|:---|:---|:---|
| `load/domain/Dataset.java` | **MODIFY** | Add `SEC_13F_HOLDING = "sec_13f_holding"`, `SEC_13F_FILER = "sec_13f_filer"` |
| `load/service/impl/SecHoldingFileLoadServiceImpl.java` | **NEW** | `@Component(Dataset.SEC_13F_HOLDING)` — DuckDB staging + upsert into `t_sec_holding`, then `CALL sp_compute_sec_holding_delta(...)` in `postProcess()` |
| `load/service/impl/SecFilerFileLoadServiceImpl.java` | **NEW** | `@Component(Dataset.SEC_13F_FILER)` — DuckDB staging + upsert into `t_sec_filer` |
| `harvester/api/dto/Fetch13FBulkRequest.java` | **NEW** | Extends `HarvesterRequest`, `requestType = "fetch_13f_bulk"` |
| `harvester/api/dto/Fetch13FCikRequest.java` | **NEW** | Extends `HarvesterRequest`, `requestType = "fetch_13f_cik"` |
| `harvester/api/dto/Fetch13FFilersRequest.java` | **NEW** | Extends `HarvesterRequest`, `requestType = "fetch_13f_filers"` |
| `harvester/api/HarvesterBatchApi.java` | **MODIFY** | Add `refresh13FBulk()`, `refresh13FCik(String cik)` |
| `harvester/service/HarvesterBatchService.java` | **MODIFY** | Implement `refresh13FBulk()`, `refresh13FCik()` using `publishRequest()` |
| `harvester/scheduler/RefreshScheduler.java` | **MODIFY** | Add `@Scheduled` method for quarterly 13F bulk + filers |
| `database/domain/PartitionConfig.java` | **MODIFY** | Add `SEC_HOLDING("t_sec_holding", PartitionType.QUARTERLY, 6, 6)` — need new `QUARTERLY` type |
| `database/domain/PartitionType.java` | **MODIFY** | Add `QUARTERLY` enum value |
| `database/service/DatabaseMaintenanceService.java` | **MODIFY** | Add `create_quarterly_partitions()` function call support |
| `common/config/OraculumProperties.java` | **MODIFY** | Add `Sec13F sec13F` record with tier1 CIKs, schedule config |
| `src/main/resources/db/migration/V*__t_sec_holding.sql` | **NEW** | Flyway migration for all 3 tables + stored procedure + indexes |
| `src/main/resources/db/migration/R__00_partition_management.sql` | **MODIFY** | Add `create_quarterly_partitions()` function + initial partition creation |
| `src/main/resources/application.yaml` | **MODIFY** | Add 13F cron schedule, tier1 CIK list config |

---

## Harvester — New Request Types

Three new request types added to the existing `AnyRequest` discriminated union.

### Existing Pattern Reference

Requests extend the `Request` base class (Pydantic `BaseModel` with `request_type` discriminator) in `common/requests/base.py`.  
On the Java side, requests extend `HarvesterRequest` (abstract class with `@JsonProperty("request_type")`, auto-generated `correlation_id` and `issued_at`).  
Requests are published via `HarvesterBatchService.publishRequest()` → `kafkaTemplate.send(harvesterRequestTopic, ...)`.

---

### 1. `fetch_13f_bulk` — Quarterly Bulk Dataset Ingestion

Downloads the SEC pre-aggregated Form 13F Bulk Dataset zip for a given quarter.

#### Kafka Request Payload

```json
{
  "request_type": "fetch_13f_bulk",
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "issued_at": "2026-05-20T14:00:00Z",
  "year": 2026,
  "quarter": 1
}
```

#### Python Pydantic Model (`common/requests/sec_13f.py`)

```python
class Fetch13FBulkRequest(Request):
    request_type: Literal["fetch_13f_bulk"] = "fetch_13f_bulk"
    year: int
    quarter: int = Field(ge=1, le=4)
```

#### Java DTO (`harvester/api/dto/Fetch13FBulkRequest.java`)

```java
@Getter
@AllArgsConstructor
@Builder
public class Fetch13FBulkRequest extends HarvesterRequest {
    private final int year;
    private final int quarter;

    @Override
    public String getRequestType() {
        return "fetch_13f_bulk";
    }
}
```

#### SEC Data Source

```
https://www.sec.gov/files/structureddata/data/form-13f-data-sets/{year}q{quarter}_13f.zip
```

Contains flat TSV files:
- `SUBMISSION.tsv` — Filing metadata (accession number, CIK, filing date, period of report)
- `COVERPAGE.tsv` — Manager name, address, report type
- `INFOTABLE.tsv` — All holdings rows for all filers in that quarter

#### Processing Steps

1. Download zip file from SEC.
2. Extract `INFOTABLE.tsv`, `SUBMISSION.tsv`, and `COVERPAGE.tsv` in memory.
3. Join INFOTABLE with SUBMISSION on `ACCESSION_NUMBER` to get `FILING_DATE`, `PERIOD_OF_REPORT`, `CIK`.
4. Join with COVERPAGE on `ACCESSION_NUMBER` to get `FILING_MANAGER_NAME`.
5. Apply value normalization:
   - If `PERIOD_OF_REPORT >= 2023-01-01`: value is already in USD (multiplier = 1).
   - If `PERIOD_OF_REPORT < 2023-01-01`: value is in thousands (multiplier = 1000).
6. Map output columns to the standardized `Sec13FHolding` domain model.
7. Write Parquet file(s) to exchange directory using existing `parquet_writer` pattern.
8. Publish `DataFileReadyEvent` to `oraculum.data_file_ready`.

#### Output `DataFileReadyEvent`

```json
{
  "event_type": "oraculum.data_file_ready",
  "dataset": "sec_13f_holding",
  "file_name": "550e8400_sec_13f_holding_part-000.parquet",
  "schema_version": 1,
  "correlation_id": "550e8400-e29b-41d4-a716-446655440000",
  "file_checksum": "sha256:abc123...",
  "record_count": 1250000,
  "file_statuses": [],
  "created_at": "2026-05-20T14:30:00Z"
}
```

---

### 2. `fetch_13f_cik` — Single CIK Real-Time Ingestion

Fetches the latest 13F-HR filing for a specific CIK via the SEC EDGAR Submissions API.

#### Kafka Request Payload

```json
{
  "request_type": "fetch_13f_cik",
  "correlation_id": "660e8400-e29b-41d4-a716-446655440001",
  "issued_at": "2026-05-15T16:00:00Z",
  "cik": "0001067983"
}
```

#### Python Pydantic Model

```python
class Fetch13FCikRequest(Request):
    request_type: Literal["fetch_13f_cik"] = "fetch_13f_cik"
    cik: str = Field(min_length=1, max_length=10, description="SEC CIK, zero-padded to 10 digits")
```

#### Java DTO

```java
@Getter
@AllArgsConstructor
@Builder
public class Fetch13FCikRequest extends HarvesterRequest {
    private final String cik;

    @Override
    public String getRequestType() {
        return "fetch_13f_cik";
    }
}
```

#### Processing Steps

1. Query `https://data.sec.gov/submissions/CIK{cik}.json`.
2. Find the most recent `13F-HR` or `13F-HR/A` in `filings.recent`.
3. Fetch the accession folder index to locate the InfoTable XML file.
4. Download and parse the InfoTable XML using `xml.etree.ElementTree`.
5. Apply value normalization based on `filing_date` (pre/post Jan 3, 2023).
6. Map to the same `Sec13FHolding` domain model.
7. Write Parquet file and publish `DataFileReadyEvent`.

---

### 3. `fetch_13f_filers` — Filer Registry Extraction

Downloads the SEC EDGAR quarterly master index to extract all CIKs that filed 13F-HR.

#### Kafka Request Payload

```json
{
  "request_type": "fetch_13f_filers",
  "correlation_id": "770e8400-e29b-41d4-a716-446655440002",
  "issued_at": "2026-05-20T15:00:00Z",
  "year": 2026,
  "quarter": 1
}
```

#### Python Pydantic Model

```python
class Fetch13FFilersRequest(Request):
    request_type: Literal["fetch_13f_filers"] = "fetch_13f_filers"
    year: int
    quarter: int = Field(ge=1, le=4)
```

#### Java DTO

```java
@Getter
@AllArgsConstructor
@Builder
public class Fetch13FFilersRequest extends HarvesterRequest {
    private final int year;
    private final int quarter;

    @Override
    public String getRequestType() {
        return "fetch_13f_filers";
    }
}
```

#### SEC Data Source

```
https://www.sec.gov/Archives/edgar/full-index/{year}/QTR{quarter}/master.zip
```

---

## Harvester — Domain Models

```python
class Sec13FHolding(BaseModel):
    """Single 13F position row."""
    accession_number: str
    cik: str
    manager_name: str
    period_of_report: date
    filing_date: date
    issuer_name: str
    class_title: str
    cusip: str
    value_usd: int
    shares_or_prn_amount: int
    shares_or_prn_type: str          # "SH" or "PRN"
    option_type: Optional[str] = None  # "PUT", "CALL", or None
    investment_discretion: str       # "SOLE", "DEFINED", "OTHER"
    voting_auth_sole: int = 0
    voting_auth_shared: int = 0
    voting_auth_none: int = 0


class Sec13FFiler(BaseModel):
    """13F institutional filer from the quarterly master index."""
    cik: str
    manager_name: str
    form_type: str
    filing_date: date
    accession_number: str
    year: int
    quarter: int
```

### Updated `DatasetType` Literal

Add to `common/domain/data_file_ready.py`:

```python
DatasetType = Literal[
    "company", "share_price", "balance_sheet", "income_statement",
    "cash_flow_statement", "insider_transaction", "ticker_document",
    "sec_13f_holding",   # NEW
    "sec_13f_filer",     # NEW
]
```

### Updated `AnyRequest` Union

Add to `common/requests/__init__.py`:

```python
AnyRequest = Annotated[
    Union[
        ...,  # existing types
        Fetch13FBulkRequest,
        Fetch13FCikRequest,
        Fetch13FFilersRequest,
    ],
    Field(discriminator="request_type"),
]
```

### Parquet Output Schema — `sec_13f_holding`

| Column | Type | Description |
| :--- | :--- | :--- |
| `accession_number` | `string` | SEC filing accession number |
| `cik` | `string` | Filer CIK (10-digit zero-padded) |
| `manager_name` | `string` | Filing manager / fund name |
| `period_of_report` | `date` | Quarter end date (e.g. 2026-03-31) |
| `filing_date` | `date` | Date filed with EDGAR |
| `issuer_name` | `string` | Held security issuer name |
| `class_title` | `string` | Class of security (COM, CL A, CL B) |
| `cusip` | `string` | 9-character CUSIP identifier |
| `value_usd` | `int64` | Market value in USD (normalized) |
| `shares_or_prn_amount` | `int64` | Number of shares or principal amount |
| `shares_or_prn_type` | `string` | `SH` (shares) or `PRN` (principal) |
| `option_type` | `string` | `PUT`, `CALL`, or empty |
| `investment_discretion` | `string` | `SOLE`, `DEFINED`, `OTHER` |
| `voting_auth_sole` | `int64` | Sole voting authority shares |
| `voting_auth_shared` | `int64` | Shared voting authority shares |
| `voting_auth_none` | `int64` | No voting authority shares |

### Parquet Output Schema — `sec_13f_filer`

| Column | Type | Description |
| :--- | :--- | :--- |
| `cik` | `string` | 10-digit zero-padded CIK |
| `manager_name` | `string` | Official EDGAR company name |
| `form_type` | `string` | `13F-HR` or `13F-HR/A` |
| `filing_date` | `date` | Date filed with SEC |
| `accession_number` | `string` | Filing accession number |
| `year` | `int32` | Filing year |
| `quarter` | `int32` | Filing quarter |

### Config Changes

Add to `config.yaml`:

```yaml
sec:
  userAgent: $ORACULUM_HARVESTER_SEC_USER_AGENT|"OraculumHarvester admin@oraculum-analytics.com"
  rateLimitPerSecond: 10
  bulkBaseUrl: "https://www.sec.gov/files/structureddata/data/form-13f-data-sets"
  submissionsBaseUrl: "https://data.sec.gov/submissions"
  archivesBaseUrl: "https://www.sec.gov/Archives/edgar"
```

---

## Oraculum (Java) — Detailed Implementation

### Existing Patterns (from codebase review)

| Pattern | Reference File | How 13F will follow it |
|:---|:---|:---|
| **Request DTO** | `HarvesterRequest.java` — abstract base, `@JsonProperty("request_type")`, auto `correlationId` + `issuedAt` | 3 new DTOs extend `HarvesterRequest` |
| **Request Publishing** | `HarvesterBatchService.publishRequest()` — `kafkaTemplate.send(harvesterRequestTopic, ...)` | Same `publishRequest()` call for 13F |
| **Scheduler** | `RefreshScheduler.java` — `@Scheduled(cron = "...")` methods calling `HarvesterBatchService` | Add `refresh13FBulk()` cron method |
| **Kafka Listener** | `DataFileReadyListener.java` — `@KafkaListener` on `data-file-ready` topic → `DataFileLoadService.processDataFileEvent()` | No change needed — existing listener handles all datasets |
| **Loader Strategy** | `@Component(Dataset.XXX)` implementing `ParquetFileLoadService` → auto-discovered by `DataFileLoadServiceImpl` via `Map<String, ParquetFileLoadService>` | New `@Component(Dataset.SEC_13F_HOLDING)` and `@Component(Dataset.SEC_13F_FILER)` |
| **DuckDB Staging** | `PostgresParquetFileLoader.loadParquetIntoTargetTable()` — DuckDB → staging table → native SQL upsert → drop staging | Same pipeline for both 13F datasets |
| **Idempotency** | `DataFileLoadServiceImpl` checks `loadLogApi.isAlreadyProcessed(dataset, correlationId, checksum)` | Works automatically for 13F |
| **Partition Management** | `PartitionConfig` enum + `DatabaseMaintenanceService.runPartitionManagement()` + Flyway `R__00_partition_management.sql` | Add `QUARTERLY` partition type |

### 1. New Dataset Constants

**File**: `com/oraculum/load/domain/Dataset.java`

```java
public static final String SEC_13F_HOLDING = "sec_13f_holding";
public static final String SEC_13F_FILER = "sec_13f_filer";
```

### 2. New Loader — `SecHoldingFileLoadServiceImpl`

**File**: `com/oraculum/load/service/impl/SecHoldingFileLoadServiceImpl.java`

```java
@Component(Dataset.SEC_13F_HOLDING)
@RequiredArgsConstructor
public class SecHoldingFileLoadServiceImpl implements ParquetFileLoadService {

    private static final String TARGET_TABLE_NAME = "t_sec_holding";
    private static final String BULK_UPSERT_SQL = """
            INSERT INTO t_sec_holding AS dest
              (accession_number, cik, manager_name, period_of_report, filing_date,
               issuer_name, class_title, cusip, value_usd,
               shares_or_prn_amount, shares_or_prn_type, option_type,
               investment_discretion, voting_auth_sole, voting_auth_shared,
               voting_auth_none, created_at)
            SELECT
               src.accession_number,
               src.cik,
               src.manager_name,
               CAST(src.period_of_report AS DATE),
               CAST(src.filing_date AS DATE),
               src.issuer_name,
               src.class_title,
               src.cusip,
               CAST(src.value_usd AS BIGINT),
               CAST(src.shares_or_prn_amount AS BIGINT),
               src.shares_or_prn_type,
               src.option_type,
               src.investment_discretion,
               CAST(src.voting_auth_sole AS BIGINT),
               CAST(src.voting_auth_shared AS BIGINT),
               CAST(src.voting_auth_none AS BIGINT),
               CURRENT_TIMESTAMP
            FROM %s AS src
            ON CONFLICT (accession_number, cusip, option_type, period_of_report)
            DO UPDATE SET
               manager_name = EXCLUDED.manager_name,
               filing_date = EXCLUDED.filing_date,
               issuer_name = EXCLUDED.issuer_name,
               class_title = EXCLUDED.class_title,
               value_usd = EXCLUDED.value_usd,
               shares_or_prn_amount = EXCLUDED.shares_or_prn_amount,
               shares_or_prn_type = EXCLUDED.shares_or_prn_type,
               investment_discretion = EXCLUDED.investment_discretion,
               voting_auth_sole = EXCLUDED.voting_auth_sole,
               voting_auth_shared = EXCLUDED.voting_auth_shared,
               voting_auth_none = EXCLUDED.voting_auth_none;
            """;

    private final PostgresParquetFileLoader postgresParquetFileLoader;
    private final JdbcTemplate jdbcTemplate;

    @Override
    public void merge(DataFileReadyEvent event) {
        var stagingTableName = PostgresParquetFileLoader.getStagingTableName(TARGET_TABLE_NAME);
        var loadParquetDto = LoadParquetDto.builder()
                .targetTableName(TARGET_TABLE_NAME)
                .stagingTableName(stagingTableName)
                .parquetFilePath(postgresParquetFileLoader.resolveAndValidatePath(event))
                .loadSql(BULK_UPSERT_SQL.formatted(stagingTableName))
                .hasStatementData(false)
                .build();
        postgresParquetFileLoader.loadParquetIntoTargetTable(loadParquetDto);
    }

    @Override
    public void postProcess(DataFileReadyEvent event) {
        // Compute deltas after holdings load
        // Determine current & previous period from the loaded data
        jdbcTemplate.execute("""
            DO $$
            DECLARE
                v_current  DATE;
                v_previous DATE;
            BEGIN
                SELECT MAX(period_of_report) INTO v_current FROM t_sec_holding;
                SELECT MAX(period_of_report) INTO v_previous
                  FROM t_sec_holding
                 WHERE period_of_report < v_current;

                IF v_current IS NOT NULL AND v_previous IS NOT NULL THEN
                    CALL sp_compute_sec_holding_delta(v_current, v_previous);
                END IF;
            END $$;
        """);
    }
}
```

### 3. New Loader — `SecFilerFileLoadServiceImpl`

**File**: `com/oraculum/load/service/impl/SecFilerFileLoadServiceImpl.java`

```java
@Component(Dataset.SEC_13F_FILER)
@RequiredArgsConstructor
public class SecFilerFileLoadServiceImpl implements ParquetFileLoadService {

    private static final String TARGET_TABLE_NAME = "t_sec_filer";
    private static final String BULK_UPSERT_SQL = """
            INSERT INTO t_sec_filer AS dest
              (cik, manager_name, tier, is_active, last_filing_date,
               last_processed_accession, created_at, updated_at)
            SELECT
               src.cik,
               src.manager_name,
               'TIER_2',
               TRUE,
               CAST(src.filing_date AS DATE),
               src.accession_number,
               CURRENT_TIMESTAMP,
               CURRENT_TIMESTAMP
            FROM %s AS src
            ON CONFLICT (cik)
            DO UPDATE SET
               manager_name = EXCLUDED.manager_name,
               last_filing_date = EXCLUDED.last_filing_date,
               last_processed_accession = EXCLUDED.last_processed_accession,
               updated_at = CURRENT_TIMESTAMP;
            """;

    private final PostgresParquetFileLoader postgresParquetFileLoader;

    @Override
    public void merge(DataFileReadyEvent event) {
        var stagingTableName = PostgresParquetFileLoader.getStagingTableName(TARGET_TABLE_NAME);
        var loadParquetDto = LoadParquetDto.builder()
                .targetTableName(TARGET_TABLE_NAME)
                .stagingTableName(stagingTableName)
                .parquetFilePath(postgresParquetFileLoader.resolveAndValidatePath(event))
                .loadSql(BULK_UPSERT_SQL.formatted(stagingTableName))
                .hasStatementData(false)
                .build();
        postgresParquetFileLoader.loadParquetIntoTargetTable(loadParquetDto);
    }
}
```

### 4. Scheduler Integration

**File**: `com/oraculum/harvester/scheduler/RefreshScheduler.java` — add new methods:

```java
// 20th of Feb, May, Aug, Nov at 6 AM — ~55 days after quarter end
@Scheduled(cron = "${oraculum.data.sec-13f.bulk-cron}")
public void refresh13FBulk() {
    log.info("Starting scheduled 13F bulk quarterly ingestion...");
    try {
        refreshService.refresh13FBulk();
    } catch (Exception e) {
        log.error("Scheduled 13F bulk refresh failed", e);
    }
}
```

**File**: `com/oraculum/harvester/service/HarvesterBatchService.java` — add new methods:

```java
@Override
public void refresh13FBulk() {
    int[] q = Sec13FUtil.getCurrentFilingQuarter();
    log.info("Requesting 13F filer registry refresh for {}Q{}", q[0], q[1]);
    publishRequest(Fetch13FFilersRequest.builder().year(q[0]).quarter(q[1]).build());

    log.info("Requesting 13F bulk holdings for {}Q{}", q[0], q[1]);
    publishRequest(Fetch13FBulkRequest.builder().year(q[0]).quarter(q[1]).build());
}

@Override
public void refresh13FCik(String cik) {
    log.info("Requesting 13F CIK-level refresh for CIK: {}", cik);
    publishRequest(Fetch13FCikRequest.builder().cik(cik).build());
}
```

### 5. Config Properties

**File**: `com/oraculum/common/config/OraculumProperties.java` — add to `Data` record:

```java
public record Data(SharePrice sharePrice,
                   News news,
                   InsiderTransactions insiderTransactions,
                   Sec13F sec13f) {  // NEW
    // ...existing records...

    public record Sec13F(String bulkCron,        // "0 0 6 20 2,5,8,11 *"
                         List<String> tier1Ciks) {
    }
}
```

**File**: `src/main/resources/application.yaml`:

```yaml
oraculum:
  data:
    sec-13f:
      bulk-cron: "0 0 6 20 2,5,8,11 *"   # 20th of Feb/May/Aug/Nov at 6am
      tier1-ciks:
        - "0001067983"  # Berkshire Hathaway
        - "0001649339"  # Scion Asset Management
        - "0001336528"  # Pershing Square
        - "0001536411"  # Duquesne Family Office
        - "0001009258"  # Appaloosa Management
        - "0001061768"  # Baupost Group
        - "0001079114"  # Greenlight Capital
        - "0000915191"  # Elliott Investment Management
        - "0001048445"  # Third Point
        - "0001099281"  # Icahn Enterprises
        - "0001423053"  # Citadel Advisors
        - "0001350694"  # Bridgewater Associates
        - "0001037389"  # Renaissance Technologies
        - "0001167483"  # Tiger Global Management
        - "0001569205"  # ARK Investment Management
```

### 6. Partition Management

**File**: `database/domain/PartitionConfig.java` — add:

```java
SEC_HOLDING("t_sec_holding", PartitionType.QUARTERLY, 3, 6);
```

> **Note**: `t_sec_holding` uses `QUARTERLY` partitions (e.g. `t_sec_holding_2026_q1`) with `period_of_report` as partition key. Only 2 partitions are kept. Since the existing `PartitionConfig` uses `monthsAhead` / `monthsToKeep`, the quarterly type will use the same fields with quarterly semantics (3 months ahead = 1 quarter ahead, 6 months to keep = 2 quarters).

**File**: `src/main/resources/db/migration/R__00_partition_management.sql` — add:

```sql
CREATE OR REPLACE FUNCTION create_quarterly_partitions(p_table_name TEXT, p_start_date DATE, p_end_date DATE)
RETURNS void AS $$
DECLARE
    v_partition_date DATE;
    v_partition_name TEXT;
    v_partition_start TEXT;
    v_partition_end TEXT;
    v_quarter INT;
BEGIN
    v_partition_date := date_trunc('quarter', p_start_date);
    WHILE v_partition_date <= p_end_date LOOP
        v_quarter := EXTRACT(QUARTER FROM v_partition_date);
        v_partition_name := p_table_name || '_' || to_char(v_partition_date, 'YYYY') || '_q' || v_quarter;
        v_partition_start := to_char(v_partition_date, 'YYYY-MM-DD');
        v_partition_end := to_char(v_partition_date + INTERVAL '3 months', 'YYYY-MM-DD');

        IF NOT EXISTS (
            SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE c.relname = v_partition_name AND n.nspname = 'public'
        ) THEN
            EXECUTE format(
                'CREATE TABLE %I PARTITION OF %I FOR VALUES FROM (%L) TO (%L)',
                v_partition_name, p_table_name, v_partition_start, v_partition_end
            );
        END IF;

        v_partition_date := v_partition_date + INTERVAL '3 months';
    END LOOP;
END;
$$ LANGUAGE plpgsql;

-- Create initial quarterly partitions for t_sec_holding
SELECT create_quarterly_partitions('t_sec_holding', (NOW() - INTERVAL '6 months')::DATE, (NOW() + INTERVAL '3 months')::DATE);
```

---

## Database Schema (PostgreSQL)

### Flyway Migration

**File**: `src/main/resources/db/migration/V*__t_sec_holding.sql`

### Storage Estimate (2 Quarters Only)

| Object | Rows | Size |
| :--- | :--- | :--- |
| `t_sec_filer` | ~6,000 | negligible |
| `t_sec_holding` (2 partitions) | ~3M | ~1.5 GB |
| `t_sec_holding_delta` | ~1.5M | ~500 MB |
| **Total** | | **~2 GB** |

---

### Table 1: `t_sec_filer` — Institutional Manager Registry

Not partitioned — ~6,000 rows max.

```sql
CREATE TABLE t_sec_filer (
    id                        BIGSERIAL      PRIMARY KEY,
    cik                       VARCHAR(10)    NOT NULL,
    manager_name              VARCHAR(500)   NOT NULL,
    tier                      VARCHAR(10)    NOT NULL DEFAULT 'TIER_2',
    is_active                 BOOLEAN        NOT NULL DEFAULT TRUE,
    last_filing_date          DATE,
    last_processed_accession  VARCHAR(25),
    created_at                TIMESTAMPTZ    NOT NULL DEFAULT NOW(),
    updated_at                TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT uq_t_sec_filer_cik UNIQUE (cik)
);

CREATE INDEX idx_t_sec_filer_tier
    ON t_sec_filer (tier) WHERE is_active = TRUE;
```

---

### Table 2: `t_sec_holding` — Quarterly Holdings (Partitioned)

```sql
CREATE TABLE t_sec_holding (
    id                        BIGSERIAL,
    cik                       VARCHAR(10)    NOT NULL,
    accession_number          VARCHAR(25)    NOT NULL,
    period_of_report          DATE           NOT NULL,
    filing_date               DATE           NOT NULL,
    manager_name              VARCHAR(500)   NOT NULL,
    issuer_name               VARCHAR(500)   NOT NULL,
    class_title               VARCHAR(200)   NOT NULL,
    cusip                     VARCHAR(9)     NOT NULL,
    value_usd                 BIGINT         NOT NULL,
    shares_or_prn_amount      BIGINT         NOT NULL,
    shares_or_prn_type        VARCHAR(3)     NOT NULL,
    option_type               VARCHAR(4),
    investment_discretion     VARCHAR(10)    NOT NULL,
    voting_auth_sole          BIGINT         NOT NULL DEFAULT 0,
    voting_auth_shared        BIGINT         NOT NULL DEFAULT 0,
    voting_auth_none          BIGINT         NOT NULL DEFAULT 0,
    created_at                TIMESTAMPTZ    NOT NULL DEFAULT NOW(),

    CONSTRAINT pk_t_sec_holding PRIMARY KEY (id, period_of_report)
) PARTITION BY RANGE (period_of_report);
```

#### Indexes

```sql
-- Deduplication: prevent re-importing the same filing row
CREATE UNIQUE INDEX uq_t_sec_holding_natural_key
    ON t_sec_holding (accession_number, cusip, option_type, period_of_report);

-- "What does Berkshire hold this quarter?"
CREATE INDEX idx_t_sec_holding_cik_period
    ON t_sec_holding (cik, period_of_report);

-- "Who holds AAPL (CUSIP 037833100) this quarter?"
CREATE INDEX idx_t_sec_holding_cusip_period
    ON t_sec_holding (cusip, period_of_report);
```

---

### Table 3: `t_sec_holding_delta` — Quarter-over-Quarter Changes

Regular table, populated by stored procedure. Truncated and recomputed after each quarterly ingestion.

Not partitioned — only holds data for the latest quarter (~1.5M rows).

```sql
CREATE TABLE t_sec_holding_delta (
    id                        BIGSERIAL      PRIMARY KEY,
    cik                       VARCHAR(10)    NOT NULL,
    manager_name              VARCHAR(500)   NOT NULL,
    period_of_report          DATE           NOT NULL,
    previous_period           DATE           NOT NULL,
    cusip                     VARCHAR(9)     NOT NULL,
    issuer_name               VARCHAR(500)   NOT NULL,
    class_title               VARCHAR(200),
    option_type               VARCHAR(4),
    change_type               VARCHAR(15)    NOT NULL,
    current_shares            BIGINT,
    current_value_usd         BIGINT,
    previous_shares           BIGINT,
    previous_value_usd        BIGINT,
    shares_change             BIGINT         NOT NULL,
    value_change              BIGINT         NOT NULL,
    shares_change_pct         DECIMAL(10,2),
    value_change_pct          DECIMAL(10,2),
    created_at                TIMESTAMPTZ    NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_t_sec_holding_delta_cik_change
    ON t_sec_holding_delta (cik, change_type);

CREATE INDEX idx_t_sec_holding_delta_cusip
    ON t_sec_holding_delta (cusip);

CREATE INDEX idx_t_sec_holding_delta_change
    ON t_sec_holding_delta (change_type);

CREATE UNIQUE INDEX uq_t_sec_holding_delta_natural_key
    ON t_sec_holding_delta (cik, cusip, option_type, period_of_report);
```

#### `change_type` values

| Value | Meaning |
| :--- | :--- |
| `NEW_POSITION` | Position did not exist in previous quarter |
| `INCREASED` | Shares increased vs previous quarter |
| `DECREASED` | Shares decreased vs previous quarter |
| `UNCHANGED` | Same share count and value (excluded by default) |
| `SOLD_OUT` | Position existed in previous quarter but not in current |

---

### Stored Procedure: `sp_compute_sec_holding_delta`

Called by Oraculum (Java) via `SecHoldingFileLoadServiceImpl.postProcess()` after ingesting a new quarter's holdings.

```sql
CREATE OR REPLACE PROCEDURE sp_compute_sec_holding_delta(
    p_current_period  DATE,
    p_previous_period DATE
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_count BIGINT;
BEGIN
    -- Clear existing delta data
    TRUNCATE TABLE t_sec_holding_delta;

    -- Compute and insert deltas
    INSERT INTO t_sec_holding_delta (
        cik, manager_name, period_of_report, previous_period,
        cusip, issuer_name, class_title, option_type,
        change_type,
        current_shares, current_value_usd,
        previous_shares, previous_value_usd,
        shares_change, value_change, shares_change_pct, value_change_pct
    )
    SELECT
        COALESCE(c.cik, p.cik),
        COALESCE(c.manager_name, p.manager_name),
        p_current_period,
        p_previous_period,
        COALESCE(c.cusip, p.cusip),
        COALESCE(c.issuer_name, p.issuer_name),
        COALESCE(c.class_title, p.class_title),
        COALESCE(c.option_type, p.option_type),

        -- Change type classification
        CASE
            WHEN p.cusip IS NULL                                     THEN 'NEW_POSITION'
            WHEN c.cusip IS NULL                                     THEN 'SOLD_OUT'
            WHEN c.shares_or_prn_amount > p.shares_or_prn_amount     THEN 'INCREASED'
            WHEN c.shares_or_prn_amount < p.shares_or_prn_amount     THEN 'DECREASED'
            ELSE 'UNCHANGED'
        END,

        -- Current quarter values
        c.shares_or_prn_amount,
        c.value_usd,

        -- Previous quarter values
        p.shares_or_prn_amount,
        p.value_usd,

        -- Absolute deltas
        COALESCE(c.shares_or_prn_amount, 0) - COALESCE(p.shares_or_prn_amount, 0),
        COALESCE(c.value_usd, 0) - COALESCE(p.value_usd, 0),

        -- Percentage changes
        CASE WHEN p.shares_or_prn_amount > 0
             THEN ROUND(
                 (COALESCE(c.shares_or_prn_amount, 0) - p.shares_or_prn_amount)
                 * 100.0 / p.shares_or_prn_amount, 2)
        END,
        CASE WHEN p.value_usd > 0
             THEN ROUND(
                 (COALESCE(c.value_usd, 0) - p.value_usd)
                 * 100.0 / p.value_usd, 2)
        END

    FROM t_sec_holding c
    FULL OUTER JOIN t_sec_holding p
        ON  c.cik = p.cik
        AND c.cusip = p.cusip
        AND COALESCE(c.option_type, '') = COALESCE(p.option_type, '')
    WHERE (c.period_of_report = p_current_period  OR c.period_of_report IS NULL)
      AND (p.period_of_report = p_previous_period OR p.period_of_report IS NULL)
      AND NOT (c.cusip IS NOT NULL AND p.cusip IS NOT NULL
               AND c.shares_or_prn_amount = p.shares_or_prn_amount
               AND c.value_usd = p.value_usd);  -- Skip truly unchanged rows

    GET DIAGNOSTICS v_count = ROW_COUNT;
    RAISE NOTICE 'Computed % delta rows for period % vs %', v_count, p_current_period, p_previous_period;
END;
$$;
```

---

## Key Queries

### Manager Portfolio View

```sql
-- "What does Berkshire Hathaway hold right now?"
SELECT issuer_name, cusip, class_title, value_usd, shares_or_prn_amount, option_type
FROM   t_sec_holding
WHERE  cik = '0001067983'
  AND  period_of_report = '2026-03-31'
ORDER BY value_usd DESC;
```

### Position Changes View

```sql
-- "What did Buffett buy/sell this quarter?"
SELECT change_type, issuer_name, cusip,
       shares_change, shares_change_pct,
       current_value_usd, value_change
FROM   t_sec_holding_delta
WHERE  cik = '0001067983'
  AND  change_type <> 'UNCHANGED'
ORDER BY change_type, ABS(value_change) DESC;
```

### Institutional Ownership View

```sql
-- "Top 20 institutional holders of Apple (CUSIP 037833100)"
SELECT manager_name, cik, shares_or_prn_amount, value_usd
FROM   t_sec_holding
WHERE  cusip = '037833100'
  AND  period_of_report = '2026-03-31'
ORDER BY value_usd DESC
LIMIT 20;
```

### Smart Money Consensus

```sql
-- "Which stocks are Tier 1 managers buying most this quarter?"
SELECT d.cusip, d.issuer_name,
       COUNT(*) FILTER (WHERE d.change_type = 'NEW_POSITION') AS new_positions,
       COUNT(*) FILTER (WHERE d.change_type = 'INCREASED')    AS increased,
       COUNT(*) FILTER (WHERE d.change_type = 'DECREASED')    AS decreased,
       COUNT(*) FILTER (WHERE d.change_type = 'SOLD_OUT')     AS sold_out,
       SUM(d.shares_change) AS net_shares_change
FROM   t_sec_holding_delta d
JOIN   t_sec_filer f ON f.cik = d.cik AND f.tier = 'TIER_1'
WHERE  d.period_of_report = '2026-03-31'
GROUP BY d.cusip, d.issuer_name
ORDER BY new_positions + increased DESC
LIMIT 30;
```

---

## Complete Data Flow Timeline (Per Quarter)

```
Quarter End (e.g. Mar 31)
    │
    ├── Day 35-45: ORACULUM polls SEC Submissions API for Tier 1 CIKs
    │       │
    │       ├── New filing detected → Kafka: fetch_13f_cik
    │       │       │
    │       │       └── HARVESTER: Download XML → Parquet → DataFileReadyEvent
    │       │               │
    │       │               └── ORACULUM: DataFileReadyListener → SecHoldingFileLoadServiceImpl
    │       │                       ├── DuckDB staging → upsert t_sec_holding
    │       │                       └── postProcess() → CALL sp_compute_sec_holding_delta
    │       │
    │       └── (repeat until filing deadline passes)
    │
    ├── Day 46: Filing deadline passed
    │
    ├── Day 55: SEC publishes Bulk Dataset zip
    │       │
    │       └── RefreshScheduler.refresh13FBulk() fires:
    │               ├── HarvesterBatchService.publishRequest(Fetch13FFilersRequest)
    │               │       └── HARVESTER → Parquet → SecFilerFileLoadServiceImpl
    │               │               └── DuckDB staging → upsert t_sec_filer
    │               │
    │               └── HarvesterBatchService.publishRequest(Fetch13FBulkRequest)
    │                       └── HARVESTER → Parquet(s) → SecHoldingFileLoadServiceImpl
    │                               ├── DuckDB staging → upsert t_sec_holding
    │                               ├── postProcess() → CALL sp_compute_sec_holding_delta
    │                               └── DatabaseMaintenanceService → drop oldest partition
    │
    └── Day 56+: Data available via API / UI
```

---

## SEC 13F Background Reference

### What is Form 13F?

Form 13F is filed quarterly by Institutional Investment Managers managing ≥$100M in 13F securities within 45 days after each calendar quarter end.

### Filing Types

- **13F-HR** (Holdings Report): Contains the actual table of holdings.
- **13F-HR/A** (Amendment): Restates or amends a previous filing.
- **13F-NT** (Notice): States that holdings are filed by another manager (contains no holdings table).

### Value Reporting Rule Change (Jan 2023)

- **Prior to Jan 3, 2023**: Position `value` was reported in **thousands** of USD.
- **Jan 3, 2023 onwards**: `value` is reported in **exact single dollars**.

The Harvester normalizes all values to single USD during processing.

### SEC Rate Limits

- SEC EDGAR enforces **10 requests per second** per User-Agent.
- A custom `User-Agent` header is required: `"CompanyName AdminEmail@domain.com"`.

### Tier 1 CIK Reference List

| Investment Manager | CIK |
| :--- | :--- |
| Berkshire Hathaway (Warren Buffett) | `0001067983` |
| Scion Asset Management (Michael Burry) | `0001649339` |
| Pershing Square Capital (Bill Ackman) | `0001336528` |
| Duquesne Family Office (Stanley Druckenmiller) | `0001536411` |
| Appaloosa Management (David Tepper) | `0001009258` |
| Baupost Group (Seth Klarman) | `0001061768` |
| Greenlight Capital (David Einhorn) | `0001079114` |
| Elliott Investment Management (Paul Singer) | `0000915191` |
| Third Point (Dan Loeb) | `0001048445` |
| Icahn Enterprises (Carl Icahn) | `0001099281` |
| Citadel Advisors (Ken Griffin) | `0001423053` |
| Bridgewater Associates (Ray Dalio) | `0001350694` |
| Renaissance Technologies | `0001037389` |
| Tiger Global Management | `0001167483` |
| ARK Investment Management (Cathie Wood) | `0001569205` |
