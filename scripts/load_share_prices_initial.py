"""Bulk-load SimFin daily share prices directly into PostgreSQL.

Bypasses Kafka entirely.  Uses psycopg3 COPY into a temporary staging
table followed by an ``ON CONFLICT`` upsert for idempotent, high-throughput
initial loading.  Safe to re-run: duplicate rows are updated in place.

Usage::

    uv run python scripts/load_share_prices_initial.py
    uv run python scripts/load_share_prices_initial.py --market us --variant daily

Prerequisites:
    1. ``alembic upgrade head`` must have been applied so ``t_share_price`` exists.
    2. ORACULUM_DATABASE_URL (or the default in config.yaml) must point to a
       running PostgreSQL instance.
    3. ORACULUM_SIMFIN_API_KEY must be set (or present in .env).
"""

from __future__ import annotations

import argparse
import logging
import math
import sys
from datetime import date, datetime, timezone
from typing import Iterator

import pandas as pd
import psycopg
import simfin as sf

from common.config import config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)
logger = logging.getLogger(__name__)

_DEFAULT_MARKET = "us"
_DEFAULT_VARIANT = "daily"
_HISTORICAL_START = date(1990, 1, 1)
_MONTHS_AHEAD = 9
_CHUNK_SIZE = 50_000

_SIMFIN_COLUMN_MAP: dict[str, str] = {
    "Ticker": "ticker",
    "SimFinId": "sim_fin_id",
    "Currency": "currency",
    "Date": "trade_date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj. Close": "adj_close",
    "Volume": "volume",
    "Shares Outstanding (Common)": "shares_outstanding",
    "Dividend": "dividend",
}

_COPY_COLUMNS = (
    "ticker", "sim_fin_id", "currency", "market", "trade_date",
    "open", "high", "low", "close", "adj_close",
    "volume", "shares_outstanding", "dividend", "extracted_at",
)

_STAGING_DDL = """
    CREATE TEMPORARY TABLE share_price_staging (
        ticker             TEXT        NOT NULL,
        sim_fin_id         INTEGER,
        currency           TEXT,
        market             TEXT        NOT NULL,
        trade_date         DATE        NOT NULL,
        open               NUMERIC,
        high               NUMERIC,
        low                NUMERIC,
        close              NUMERIC,
        adj_close          NUMERIC,
        volume             BIGINT,
        shares_outstanding BIGINT,
        dividend           NUMERIC,
        extracted_at       TIMESTAMPTZ NOT NULL
    )
"""

_COPY_SQL = (
    "COPY share_price_staging"
    " (ticker, sim_fin_id, currency, market, trade_date,"
    "  open, high, low, close, adj_close,"
    "  volume, shares_outstanding, dividend, extracted_at)"
    " FROM STDIN"
)

_UPSERT_SQL = """
    INSERT INTO t_share_price (
        ticker, sim_fin_id, currency, market, trade_date,
        open, high, low, close, adj_close,
        volume, shares_outstanding, dividend, extracted_at
    )
    SELECT
        ticker, sim_fin_id, currency, market, trade_date,
        open, high, low, close, adj_close,
        volume, shares_outstanding, dividend, extracted_at
    FROM share_price_staging
    ON CONFLICT (ticker, market, trade_date) DO UPDATE SET
        sim_fin_id         = EXCLUDED.sim_fin_id,
        currency           = EXCLUDED.currency,
        open               = EXCLUDED.open,
        high               = EXCLUDED.high,
        low                = EXCLUDED.low,
        close              = EXCLUDED.close,
        adj_close          = EXCLUDED.adj_close,
        volume             = EXCLUDED.volume,
        shares_outstanding = EXCLUDED.shares_outstanding,
        dividend           = EXCLUDED.dividend,
        extracted_at       = EXCLUDED.extracted_at
"""


def _psycopg_url(sqlalchemy_url: str) -> str:
    """Strip the SQLAlchemy dialect prefix so psycopg3 accepts the URL."""
    return sqlalchemy_url.replace("postgresql+psycopg://", "postgresql://", 1)


def _configure_simfin() -> None:
    cache_path = config.harvester_data_path / "simfin_cache"
    cache_path.mkdir(parents=True, exist_ok=True)
    sf.set_api_key(config.simfin_api_key)
    sf.set_data_dir(str(cache_path))


def _patch_pandas() -> None:
    """Remove the ``date_parser`` kwarg that SimFin passes to Pandas 2+."""
    original = pd.read_csv

    def _patched(*args, **kwargs):  # type: ignore[no-untyped-def]
        kwargs.pop("date_parser", None)
        return original(*args, **kwargs)

    pd.read_csv = _patched  # type: ignore[assignment]


def _load_dataframe(market: str, variant: str) -> pd.DataFrame:
    logger.info("Loading share prices variant=%s market=%s ...", variant, market)
    df = sf.load_shareprices(variant=variant, market=market).reset_index()
    logger.info("Loaded %d rows from SimFin cache", len(df))
    return df


def _prepare_rows(
    df: pd.DataFrame, market: str, extracted_at: datetime
) -> Iterator[tuple]:
    """Yield one COPY-ready tuple per DataFrame row with NaN coerced to None."""
    df = df.rename(columns=_SIMFIN_COLUMN_MAP)
    df["market"] = market
    df["extracted_at"] = extracted_at

    # Ensure every expected column is present
    for col in _COPY_COLUMNS:
        if col not in df.columns:
            df[col] = None

    # Convert pd.Timestamp → datetime.date for the partition key
    df["trade_date"] = pd.to_datetime(df["trade_date"]).dt.date

    for row in df[list(_COPY_COLUMNS)].itertuples(index=False, name=None):
        yield tuple(
            None if (isinstance(v, float) and math.isnan(v)) else v
            for v in row
        )


def _next_month(d: date) -> date:
    return date(d.year + 1, 1, 1) if d.month == 12 else date(d.year, d.month + 1, 1)


def _add_months(d: date, n: int) -> date:
    total = d.month - 1 + n
    return date(d.year + total // 12, total % 12 + 1, 1)


def _ensure_partitions(conn: psycopg.Connection) -> None:
    """Create any missing monthly partitions from 1990-01 through now+9 months."""
    today = date.today()
    end = _add_months(date(today.year, today.month, 1), _MONTHS_AHEAD + 1)

    with conn.cursor() as cur:
        cur.execute(
            "SELECT tablename FROM pg_tables"
            " WHERE schemaname = 'public' AND tablename LIKE 't_share_price_%'"
        )
        existing = {row[0] for row in cur.fetchall()}

    current = date(_HISTORICAL_START.year, _HISTORICAL_START.month, 1)
    created = 0
    with conn.cursor() as cur:
        while current < end:
            name = f"t_share_price_{current.year:04d}_{current.month:02d}"
            if name not in existing:
                nm = _next_month(current)
                cur.execute(
                    f"CREATE TABLE IF NOT EXISTS {name}"
                    f" PARTITION OF t_share_price"
                    f" FOR VALUES FROM ('{current.isoformat()}')"
                    f" TO ('{nm.isoformat()}')"
                )
                created += 1
            current = _next_month(current)

    conn.commit()
    logger.info("Partitions ensured: created=%d", created)


def _create_staging_table(conn: psycopg.Connection) -> None:
    with conn.cursor() as cur:
        cur.execute(_STAGING_DDL)
    conn.commit()


def _copy_chunk(conn: psycopg.Connection, chunk: list[tuple]) -> None:
    """Truncate staging, COPY chunk, upsert into t_share_price, commit."""
    with conn.cursor() as cur:
        cur.execute("TRUNCATE TABLE share_price_staging")
    with conn.copy(_COPY_SQL) as copy:
        for row in chunk:
            copy.write_row(row)
    with conn.cursor() as cur:
        cur.execute(_UPSERT_SQL)
    conn.commit()


def main() -> None:
    """Entry point: parse args, load data, bulk-upsert into t_share_price."""
    parser = argparse.ArgumentParser(
        description="Bulk-load SimFin share prices into PostgreSQL."
    )
    parser.add_argument("--market", default=_DEFAULT_MARKET, help="SimFin market (default: us)")
    parser.add_argument("--variant", default=_DEFAULT_VARIANT, help="SimFin variant (default: daily)")
    args = parser.parse_args()

    _patch_pandas()
    _configure_simfin()

    df = _load_dataframe(args.market, args.variant)
    extracted_at = datetime.now(timezone.utc)

    logger.info("Preparing rows ...")
    all_rows = list(_prepare_rows(df, args.market, extracted_at))
    total = len(all_rows)
    logger.info("Prepared %d rows", total)

    db_url = _psycopg_url(config.database_url)
    logger.info("Connecting to database ...")

    with psycopg.connect(db_url) as conn:
        _ensure_partitions(conn)
        _create_staging_table(conn)

        upserted = 0
        for start in range(0, total, _CHUNK_SIZE):
            chunk = all_rows[start : start + _CHUNK_SIZE]
            _copy_chunk(conn, chunk)
            upserted += len(chunk)
            logger.info("  upserted %d / %d rows (%.1f%%)", upserted, total, 100 * upserted / total)

    logger.info(
        "Done. market=%s variant=%s total_rows=%d",
        args.market,
        args.variant,
        total,
    )


if __name__ == "__main__":
    main()
