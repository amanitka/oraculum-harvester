# Derived Dataset Implementation Plan

## Goal

Add a new `derived` dataset that follows the same end-to-end pattern as the existing datasets.

- **Request comes via Kafka** on the harvester request topic.
- **Harvester receives request** like `fetch_derived`.
- **SimFin provider downloads source statement files** for a given `market`, `variant`, and template selection.
- **Provider calculates derived metrics and ratios** from income, balance sheet, and cash flow data.
- **Harvester writes derived rows to Parquet** under the shared folder.
- **Harvester publishes `DataFileReadyEvent`** when parquet is ready.
- **Analyst consumes `DataFileReadyEvent`** and loads parquet into relational table `t_derived`.

## Key Design Decisions

### Dataset name

Use:

```text
derived
```

This keeps naming consistent with existing datasets:

```text
ticker
share_price
income_statement
balance_sheet
cash_flow_statement
derived
```

### Request type

Add:

```text
fetch_derived
```

New request class:

```text
FetchDerivedRequest
```

Fields:

- **`market: str = "us"`**
- **`variant: Literal["annual", "quarterly", "ttm"] = "annual"`**
- **`templates: list[DerivedTemplate]`**

### Template handling

Recommendation: start with only:

```text
general
```

Reason: the prototype formulas use SimFin general-statement fields such as:

- **`NET_INCOME`**
- **`INTEREST_EXP_NET`**
- **`INCOME_TAX`**
- **`DEPR_AMOR`**
- **`NET_CASH_OPS`**
- **`CAPEX`**
- **`TOTAL_CUR_ASSETS`**
- **`TOTAL_LIABILITIES`**
- **`TOTAL_EQUITY`**
- **`REVENUE`**

Banks and insurance templates may have different financial statement semantics, so derived ratios should not be blindly applied until formulas are reviewed.

Recommended phase split:

- **Phase 1:** support only `general`.
- **Future phase:** add `banks` and `insurance` formulas separately.

If exact statement-request shape is preferred, still include `templates`, but default it to `["general"]`.

## Future Table Shape: `t_derived`

Use a wide typed table, not JSON-only, because derived metrics will likely be queried, sorted, filtered, and charted.

### Core identity columns

Same statement identity pattern:

```text
id
composite_key
ticker
simfin_id
template
variant
currency
fiscal_year
fiscal_period
report_date
publish_date
restated_date
extracted_at
```

### Derived metric columns

Initial metric set from the prototype:

```text
ebitda
free_cash_flow
ncav
net_net_working_capital
shares_stabilized
return_on_equity
net_margin
revenue
net_income
```

### Audit columns

Same as other analyst tables:

```text
created_at
updated_at
```

### Constraints and indexes

- **Primary key:** `id`
- **Unique constraint:** `uq_derived_composite_key`
- **Indexes:**
  - **`ix_t_derived_composite_key`**
  - **`ix_t_derived_ticker`**
  - **`ix_t_derived_simfin_id`**
  - **`ix_t_derived_variant`**
  - **Optional later:** `ix_t_derived_ticker_variant_report_date`

## Step-by-Step Execution Plan

### Step 1: Add common domain model

Create:

```text
common/domain/derived.py
```

Add:

```text
Derived
DerivedTemplate
StatementVariant
```

The `Derived` Pydantic model should contain:

- **Statement identity fields**
- **`extracted_at`**
- **Typed nullable metric fields**
- **Computed `composite_key`**

The composite key should follow the same convention as statements:

```text
AAPL-2023-FY-general-annual
```

Fields:

```text
template
variant
ticker
simfin_id
currency
fiscal_year
fiscal_period
report_date
publish_date
restated_date
extracted_at
ebitda
free_cash_flow
ncav
net_net_working_capital
shares_stabilized
return_on_equity
net_margin
revenue
net_income
composite_key
```

Also update:

```text
common/domain/__init__.py
```

Export:

```text
Derived
DerivedTemplate
```

### Step 2: Add request schema

Create:

```text
common/requests/derived.py
```

Add:

```text
FetchDerivedRequest
```

Proposed schema:

```text
request_type = "fetch_derived"
market = "us"
variant = "annual" | "quarterly" | "ttm"
templates = ["general"]
```

Then update:

```text
common/requests/__init__.py
```

Changes:

- **Import `FetchDerivedRequest`**
- **Add it to `AnyRequest`**
- **Add it to `__all__`**

This makes FastStream able to deserialize incoming Kafka messages into the correct request class.

### Step 3: Extend `DataFileReadyEvent`

Update:

```text
common/domain/data_file_ready.py
```

Add `"derived"` to `DatasetType`.

Current set:

```text
ticker
share_price
balance_sheet
income_statement
cash_flow_statement
```

New set:

```text
ticker
share_price
balance_sheet
income_statement
cash_flow_statement
derived
```

This lets harvester publish and analyst consume parquet-ready events for derived data.

### Step 4: Implement provider calculation

Update:

```text
harvester/providers/simfin_provider.py
```

Add method:

```text
fetch_derived(
    template: DerivedTemplate,
    variant: str,
    market: str,
) -> Iterator[Derived]
```

Provider flow:

1. **Load income dataframe.**
2. **Load balance sheet dataframe.**
3. **Load cash flow dataframe.**
4. **Reset indexes.**
5. **Merge by statement identity keys.**
6. **Calculate derived metrics.**
7. **Validate each output row into `Derived`.**
8. **Yield valid rows.**

#### Merge keys

Use identity columns common to all three statements:

```text
Ticker
SimFinId
Currency
Fiscal Year
Fiscal Period
Report Date
Publish Date
Restated Date
```

Important detail: `Restated Date` may be absent or null, so implementation should handle it carefully.

Safer approach:

- **Ensure `Restated Date` exists in all frames.**
- **Use normalized join keys.**
- **Avoid accidentally dropping all rows because one source lacks restated date.**

#### Division safety

Ratios must not produce `inf` or `-inf`.

For:

```text
return_on_equity = net_income / total_equity
net_margin = net_income / revenue
```

Use safe divide:

- **Denominator missing:** `None`
- **Denominator zero:** `None`
- **Result NaN/inf:** `None`

#### Metric formulas

Initial formulas:

```text
ebitda =
    net_income
    - interest_expense_net
    - income_tax
    + depreciation_amortization

free_cash_flow =
    net_cash_from_operating_activities
    + capital_expenditure

ncav =
    total_current_assets
    - total_liabilities

net_net_working_capital =
    cash_cash_equivalents_short_term_investments
    + accounts_notes_receivable * 0.75
    + inventories * 0.5
    - total_liabilities

shares_stabilized =
    shares_diluted if present else shares_basic

return_on_equity =
    net_income / total_equity

net_margin =
    net_income / revenue
```

Use SimFin column constants from `simfin.names`.

### Step 5: Add harvester service

Create:

```text
harvester/services/derived.py
```

Add:

```text
DerivedService
```

Pattern should mirror `IncomeStatementService`, `BalanceSheetService`, and `CashFlowStatementService`.

Flow:

1. **Iterate requested templates.**
2. **Call provider in worker thread:**

```text
self._provider.fetch_derived(...)
```

3. **Write rows to parquet:**

```text
write_to_parquet(
    models=rows,
    dataset="derived",
    run_id=run_id,
    template=template,
    variant=request.variant,
)
```

4. **Publish `DataFileReadyEvent`:**

```text
dataset="derived"
template=template
variant=request.variant
```

5. **Publish key:**

```text
derived:<run_id>
```

Update:

```text
harvester/services/__init__.py
```

Export `DerivedService`.

### Step 6: Wire harvester Kafka subscriber

Update:

```text
harvester/subscribers/request.py
```

Changes:

- **Import `FetchDerivedRequest`**
- **Import `DerivedService`**
- **Instantiate:**

```text
_derived_service = DerivedService(_provider)
```

- **Add match case:**

```text
case FetchDerivedRequest():
    await _derived_service.fetch_and_publish(request)
```

Now `fetch_derived` messages will be consumed by harvester.

### Step 7: Add analyst DB model

Create:

```text
analyst/infrastructure/models/derived.py
```

Add:

```text
DerivedDB
```

This should mirror statement DB model style but with typed derived metric columns instead of JSONB payload.

Fields:

```text
id
composite_key
ticker
simfin_id
template
variant
currency
fiscal_year
fiscal_period
report_date
publish_date
restated_date
extracted_at
ebitda
free_cash_flow
ncav
net_net_working_capital
shares_stabilized
return_on_equity
net_margin
revenue
net_income
created_at
updated_at
```

Update:

```text
analyst/infrastructure/models/__init__.py
```

Import and export `DerivedDB`.

### Step 8: Add analyst parquet loader strategy

Create:

```text
analyst/infrastructure/loaders/derived.py
```

Add:

```text
DerivedStrategy
```

Pattern:

1. **Create temp table from `t_derived`.**
2. **Drop `created_at` / `updated_at` NOT NULL in temp table.**
3. **Insert parquet records into staging table.**
4. **Upsert into `t_derived` on `composite_key`.**

Conflict update should refresh:

```text
simfin_id
currency
report_date
publish_date
restated_date
extracted_at
ebitda
free_cash_flow
ncav
net_net_working_capital
shares_stabilized
return_on_equity
net_margin
revenue
net_income
updated_at
```

Update:

```text
analyst/infrastructure/loaders/factory.py
```

Add:

```text
"derived": DerivedStrategy()
```

This lets `ParquetLoader` automatically dispatch `DataFileReadyEvent(dataset="derived")`.

### Step 9: Add Alembic migration

Create new migration:

```text
alembic/versions/0002_add_derived_table.py
```

Upgrade:

- **Create `t_derived`.**
- **Add unique constraint `uq_derived_composite_key`.**
- **Add indexes.**

Downgrade:

- **Drop `t_derived`.**

Important naming convention from project rules:

- **Table:** `t_derived`
- **Unique constraint:** `uq_derived_composite_key`
- **Indexes:** use `ix_...`

### Step 10: Add scheduled refresh support

Update:

```text
analyst/jobs/data_refresh.py
```

Add:

```text
FetchDerivedRequest
```

Update `_build_fundamentals_requests()` so for each market and variant it also appends:

```text
FetchDerivedRequest(market=market, variant=variant)
```

Updated fundamentals request list per variant:

```text
income_statement
balance_sheet
cash_flow_statement
derived
```

Sequencing note:

- **Derived calculation independently downloads the same SimFin source files.**
- **It does not depend on the analyst DB already having income/balance/cashflow loaded.**
- **Therefore it can be scheduled alongside other fundamentals requests safely.**

### Step 11: Add UI trigger support

Update:

```text
ui/application/refresh_request_factory.py
```

Add:

```text
build_derived_request(...)
```

Then update:

```text
ui/app.py
```

Add a new tab:

```text
Derived
```

Use the same statement form renderer:

```text
_render_statement_form(
    form_key="refresh_derived_form",
    title="Derived ratios refresh",
    submit_label="Queue derived refresh",
    build_request=build_derived_request,
)
```

This keeps manual triggering consistent with the existing UI.

### Step 12: Add tests

#### Harvester service test

Extend or add:

```text
tests/harvester/services/test_statement_service_provider_dispatch.py
```

Add test:

```text
test_derived_service_dispatches_to_provider_method
```

Verify:

- **Service calls `fetch_derived`.**
- **Passes `market`.**
- **Passes `variant`.**
- **Passes `template`.**
- **Writes dataset `"derived"`.**
- **Publishes Kafka key `derived:<correlation_id>`.**

#### Common request parsing test

Since `tests/common` does not exist, create:

```text
tests/common/requests/test_parse_request.py
```

Verify:

- **`parse_request({"request_type": "fetch_derived", ...})`**
- **Returns `FetchDerivedRequest`.**

#### Analyst loader test

Add:

```text
tests/analyst/infrastructure/loaders/test_derived_loader.py
```

Verify:

- **`DerivedStrategy.merge()` executes staging insert.**
- **Insert SQL references expected columns.**
- **No JSONB payload binding is required.**
- **Conflict target is `composite_key`.**

#### Provider calculation test

Add:

```text
tests/harvester/providers/test_simfin_provider_derived.py
```

Use monkeypatch/fake dataframes to avoid SimFin network/cache dependency.

Verify:

- **Income/balance/cashflow rows merge correctly.**
- **Formulas produce expected values.**
- **Divide-by-zero produces `None`.**
- **Output model has expected `composite_key`.**
- **`variant` is preserved.**

## Execution Order

Recommended order for actual implementation:

1. **Common schemas**
   - `common/domain/derived.py`
   - `common/domain/__init__.py`
   - `common/requests/derived.py`
   - `common/requests/__init__.py`
   - `common/domain/data_file_ready.py`

2. **Harvester pipeline**
   - `harvester/providers/simfin_provider.py`
   - `harvester/services/derived.py`
   - `harvester/services/__init__.py`
   - `harvester/subscribers/request.py`

3. **Analyst persistence**
   - `analyst/infrastructure/models/derived.py`
   - `analyst/infrastructure/models/__init__.py`
   - `analyst/infrastructure/loaders/derived.py`
   - `analyst/infrastructure/loaders/factory.py`
   - `alembic/versions/0002_add_derived_table.py`

4. **Schedulers and UI**
   - `analyst/jobs/data_refresh.py`
   - `ui/application/refresh_request_factory.py`
   - `ui/app.py`

5. **Tests**
   - Provider formula test
   - Service dispatch test
   - Request parsing test
   - Loader test

6. **Verification**
   - Focused tests
   - Compile/import check
   - `ruff check` and `ruff format --check` if available
   - `mypy --strict` for touched packages if practical

## Open Questions Before Execution

### 1. Should `derived` initially support only `general`?

Recommendation: **yes**.

Reason: bank and insurance statements need separate formulas.

### 2. Should `t_derived` include a `payload` JSONB column?

Recommendation: **no for now**.

Reason: derived metrics are the primary data and should be typed columns. If later traceability is needed, add:

```text
source_payload JSONB
```

or:

```text
calculation_metadata JSONB
```

Do not add it until needed.

### 3. Should the scheduler request `derived` automatically?

Recommendation: **yes**.

Reason: derived belongs to fundamentals and should refresh together with statements.

## Summary

The implementation will add a full end-to-end `derived` dataset:

- **Kafka request:** `fetch_derived`
- **Harvester service:** downloads SimFin statements and calculates ratios
- **Parquet dataset:** `derived`
- **Kafka completion event:** `DataFileReadyEvent(dataset="derived")`
- **Analyst table:** `t_derived`
- **Loader strategy:** `DerivedStrategy`
- **Scheduler/UI:** able to trigger derived refreshes

If this plan is approved, execute it in the order above, starting with common schemas and keeping each patch small.
