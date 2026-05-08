# Guide: Calculating Derived Financial Metrics Locally with SimFin

This guide provides a step-by-step walkthrough for computing derived financial metrics, such as EBITDA, ROE, and P/E ratios, locally using the `simfin` Python package. The implementation should follow the established data processing patterns within the `oraculum` project.

---

## 1. Core Calculation Logic

The following steps outline the core logic that the `harvester` service will execute upon receiving a `DerivedSignalsRefreshRequested` event.

**Note:** The `simfin` library is already initialized with the correct API key and data directory by the application's configuration. The code below should be integrated into a `harvester` component that has access to this pre-configured state.

### Step 1.1: Load Raw Financial Statements

The fundamental "building blocks" are required: the Income Statement, Balance Sheet, and Cash Flow Statement. The `ttm` (Trailing Twelve Months) variant is used for a smoother and more current analysis.

```python
# This code will run inside the harvester service.
# It relies on the application's existing SimFin configuration.
import simfin as sf
from simfin.names import *

# Load the primary datasets for the US market
# Using 'ttm' provides a rolling 12-month view of performance.
df_income = sf.load_income(variant='ttm', market='us')
df_balance = sf.load_balance(variant='ttm', market='us')
df_cashflow = sf.load_cashflow(variant='ttm', market='us')
```

### Step 1.2: Calculate Financial Signals

The `sf.fin_signals` function calculates a comprehensive set of financial ratios from the raw data.

```python
# This computes ROE, ROA, Net Profit Margin, etc., on the local machine.
df_financial_signals = sf.fin_signals(
    df_income=df_income,
    df_balance=df_balance,
    df_cashflow=df_cashflow
)

# Example of accessing a column
roe = df_financial_signals[ROE]
```

### Step 1.3: Calculate Valuation Signals

For valuation ratios that depend on the share price, price data must also be loaded. The `StockHub` object is the recommended way to manage the complex task of aligning daily prices with financial report dates.

```python
# 1. Load daily share price data
df_prices = sf.load_shareprices(variant='daily', market='us')

# 2. Use a StockHub to compute valuation signals
# A StockHub helps manage and cache data for a specific market.
hub = sf.StockHub(market='us', refresh_days=30)
df_valuation_signals = hub.val_signals(df_prices=df_prices, df_income=df_income)

# Example of accessing a column
pe_ratio = df_valuation_signals[PE_RATIO]
```

---

## 2. Automated Implementation Guide

This section outlines the plan for integrating the local calculation of derived signals into a fully automated, re-triggerable job, following the project's established architectural patterns.

### 2.1. Adherence to Existing Patterns

The implementation **must** follow the same event-driven, multi-stage processing pipeline used by existing data refresh jobs (`refresh_tickers`, `refresh_prices`). The core principle is the separation of concerns:

-   **`analyst`**: Triggers the process by sending a Kafka event.
-   **`harvester`**: Responds to the event, performs the heavy lifting (data download and calculation), and persists the result as a Parquet file.
-   **`loader`**: Responds to the harvester's output and loads the final data into the database.

This ensures the new functionality is scalable, maintainable, and consistent with the rest of the system.

### 2.2. Workflow Overview

1.  **Trigger**: A new scheduled job, `refresh_derived_signals`, runs in the `analyst` service on a configurable cron schedule.
2.  **Dispatch**: The job publishes a `DerivedSignalsRefreshRequested` event to a Kafka topic.
3.  **Harvest & Process**: The `harvester` service consumes this event. It uses its existing, application-configured `simfin` instance to perform the downloads and calculations outlined in Section 1.
4.  **Persist**: The harvester converts the two resulting DataFrames (`df_financial_signals` and `df_valuation_signals`) into two separate Parquet files and saves them to a shared location.
5.  **Load**: A final event is sent to trigger the `loader` service, which reads the Parquet files and bulk-loads the data into the new database tables.

### 2.3. Analyst Service: Scheduling the Job

**File to Modify**: `analyst/jobs/data_refresh.py`

**Changes Required**:

1.  **Add a new Job ID**:
    ```python
    _REFRESH_DERIVED_SIGNALS_JOB_ID: str = "refresh_derived_signals"
    ```

2.  **Create a new publisher function**:
    ```python
    async def refresh_derived_signals(broker: KafkaBroker) -> None:
        """Publish a message to the broker to trigger derived signals refresh."""
        # Event to be defined in common/domain/events.py
        event = DerivedSignalsRefreshRequested(
            event_id=str(uuid4()),
            full_history=False, 
        )
        await broker.publish(event)
        logger.info("Published DerivedSignalsRefreshRequested event")
    ```

3.  **Add the job to the scheduler**:
    ```python
    # Inside create_data_refresh_scheduler:
    _add_data_refresh_job(
        scheduler,
        job_id=_REFRESH_DERIVED_SIGNALS_JOB_ID,
        cron_expression=refresh.derived_signals_cron, # Add to config
        job=refresh_derived_signals,
        broker=broker,
    )
    ```

### 2.4. Database Schema Design

The calculated signals will be stored in two new PostgreSQL tables.

**Table 1: `t_financial_signals`**
-   **Description**: Stores time-series of non-price-based financial ratios (e.g., ROE, ROA, margins).
-   **Columns**:
    -   `ticker`: `VARCHAR(10)`
    -   `report_date`: `DATE`
    -   `extracted_at`: `TIMESTAMP WITH TIME ZONE`
    -   `return_on_equity`: `NUMERIC(18, 6)`
    -   `return_on_assets`: `NUMERIC(18, 6)`
    -   `net_profit_margin`: `NUMERIC(18, 6)`
    -   `debt_to_equity_ratio`: `NUMERIC(18, 6)`
    -   `(other signals as needed)`
-   **Primary Key**: `pk_financial_signals (ticker, report_date)`

**Table 2: `t_valuation_signals`**
-   **Description**: Stores time-series of valuation ratios that depend on market prices (e.g., P/E, P/S).
-   **Columns**:
    -   `ticker`: `VARCHAR(10)`
    -   `report_date`: `DATE`
    -   `extracted_at`: `TIMESTAMP WITH TIME ZONE`
    -   `price_to_earnings_ratio`: `NUMERIC(18, 6)`
    -   `price_to_sales_ratio`: `NUMERIC(18, 6)`
    -   `price_to_book_ratio`: `NUMERIC(18, 6)`
    -   `earnings_yield`: `NUMERIC(18, 6)`
    -   `(other signals as needed)`
-   **Primary Key**: `pk_valuation_signals (ticker, report_date)`
