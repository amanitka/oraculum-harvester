"""Initial schema

Revision ID: 0001_initial
Revises:
Create Date: 2026-05-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB
import sqlmodel

# revision identifiers, used by Alembic.
revision: str = "0001_initial"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # 1. t_ingestion_run_log
    op.create_table(
        "t_ingestion_run_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("run_id", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("file_checksum", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("loaded_rows", sa.Integer(), nullable=False),
        sa.Column("merged_rows", sa.Integer(), nullable=False),
        sa.Column("duration_ms", sa.Integer(), nullable=False),
        sa.Column("error_text", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("dataset", "run_id", "file_checksum", name="uq_run_log_idempotency"),
    )
    op.create_index(
        op.f("ix_t_ingestion_run_log_dataset"),
        "t_ingestion_run_log",
        ["dataset"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_ingestion_run_log_run_id"),
        "t_ingestion_run_log",
        ["run_id"],
        unique=False,
    )

    # 2. t_ticker
    op.create_table(
        "t_ticker",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("provider_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("provider_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("company_name", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("industry_id", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("industry_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("sector_name", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("isin", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("description", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("employee_count", sa.BigInteger(), nullable=True),
        sa.Column("market", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("cik", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "market", name="uq_ticker_ticker_market"),
    )
    op.create_index(op.f("ix_t_ticker_ticker"), "t_ticker", ["ticker"], unique=False)

    # 3. t_balance_sheet
    op.create_table(
        "t_balance_sheet",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("composite_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("simfin_id", sa.Integer(), nullable=False),
        sa.Column("template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("variant", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("restated_date", sa.Date(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("composite_key", name="uq_balance_sheet_composite_key"),
    )
    op.create_index(
        op.f("ix_t_balance_sheet_composite_key"),
        "t_balance_sheet",
        ["composite_key"],
        unique=False,
    )
    op.create_index(op.f("ix_t_balance_sheet_ticker"), "t_balance_sheet", ["ticker"], unique=False)
    op.create_index(
        op.f("ix_t_balance_sheet_simfin_id"),
        "t_balance_sheet",
        ["simfin_id"],
        unique=False,
    )
    op.create_index(op.f("ix_t_balance_sheet_variant"), "t_balance_sheet", ["variant"], unique=False)

    # 4. t_cash_flow_statement
    op.create_table(
        "t_cash_flow_statement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("composite_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("simfin_id", sa.Integer(), nullable=False),
        sa.Column("template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("variant", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("restated_date", sa.Date(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("composite_key", name="uq_cash_flow_statement_composite_key"),
    )
    op.create_index(
        op.f("ix_t_cash_flow_statement_composite_key"),
        "t_cash_flow_statement",
        ["composite_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_cash_flow_statement_ticker"),
        "t_cash_flow_statement",
        ["ticker"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_cash_flow_statement_simfin_id"),
        "t_cash_flow_statement",
        ["simfin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_cash_flow_statement_variant"),
        "t_cash_flow_statement",
        ["variant"],
        unique=False,
    )

    # 5. t_income_statement
    op.create_table(
        "t_income_statement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("composite_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("simfin_id", sa.Integer(), nullable=False),
        sa.Column("template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("variant", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("restated_date", sa.Date(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.Column("payload", JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("composite_key", name="uq_income_statement_composite_key"),
    )
    op.create_index(
        op.f("ix_t_income_statement_composite_key"),
        "t_income_statement",
        ["composite_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_income_statement_ticker"),
        "t_income_statement",
        ["ticker"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_income_statement_simfin_id"),
        "t_income_statement",
        ["simfin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_income_statement_variant"),
        "t_income_statement",
        ["variant"],
        unique=False,
    )

    # 6. t_share_price (partitioned)
    op.create_table(
        "t_share_price",
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("market", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("trade_date", sa.Date(), nullable=False),
        sa.Column("sim_fin_id", sa.Integer(), nullable=True),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=True),
        sa.Column("open", sa.Float(), nullable=True),
        sa.Column("high", sa.Float(), nullable=True),
        sa.Column("low", sa.Float(), nullable=True),
        sa.Column("close", sa.Float(), nullable=True),
        sa.Column("adj_close", sa.Float(), nullable=True),
        sa.Column("volume", sa.Integer(), nullable=True),
        sa.Column("shares_outstanding", sa.Integer(), nullable=True),
        sa.Column("dividend", sa.Float(), nullable=True),
        sa.Column("extracted_at", sa.DateTime(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("ticker", "market", "trade_date"),
        sa.UniqueConstraint("ticker", "market", "trade_date", name="uq_share_price_composite"),
        postgresql_partition_by="RANGE (trade_date)",
    )
    op.create_index(
        op.f("ix_share_price_market_trade_date"),
        "t_share_price",
        ["market", "trade_date"],
        unique=False,
    )
    op.create_index(op.f("ix_share_price_ticker"), "t_share_price", ["ticker"], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DROP TABLE IF EXISTS t_share_price CASCADE"))

    op.drop_table("t_income_statement")
    op.drop_table("t_cash_flow_statement")
    op.drop_table("t_balance_sheet")
    op.drop_table("t_ticker")
    op.drop_table("t_ingestion_run_log")
