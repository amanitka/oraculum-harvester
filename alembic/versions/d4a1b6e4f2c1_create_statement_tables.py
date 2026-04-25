"""create_statement_tables

Revision ID: d4a1b6e4f2c1
Revises: 7efecbfca034
Create Date: 2026-04-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "d4a1b6e4f2c1"
down_revision: Union[str, Sequence[str], None] = "7efecbfca034"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "balance_sheet",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("composite_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("simfin_id", sa.Integer(), nullable=False),
        sa.Column("template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("restated_date", sa.Date(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("composite_key", name="uq_balance_sheet_composite_key"),
    )
    op.create_index(
        op.f("ix_balance_sheet_composite_key"),
        "balance_sheet",
        ["composite_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_balance_sheet_ticker"),
        "balance_sheet",
        ["ticker"],
        unique=False,
    )
    op.create_index(
        op.f("ix_balance_sheet_simfin_id"),
        "balance_sheet",
        ["simfin_id"],
        unique=False,
    )

    op.create_table(
        "cash_flow_statement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("composite_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("simfin_id", sa.Integer(), nullable=False),
        sa.Column("template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("restated_date", sa.Date(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("composite_key", name="uq_cash_flow_statement_composite_key"),
    )
    op.create_index(
        op.f("ix_cash_flow_statement_composite_key"),
        "cash_flow_statement",
        ["composite_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cash_flow_statement_ticker"),
        "cash_flow_statement",
        ["ticker"],
        unique=False,
    )
    op.create_index(
        op.f("ix_cash_flow_statement_simfin_id"),
        "cash_flow_statement",
        ["simfin_id"],
        unique=False,
    )

    op.create_table(
        "income_statement",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("composite_key", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("ticker", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("simfin_id", sa.Integer(), nullable=False),
        sa.Column("template", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("currency", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("fiscal_year", sa.Integer(), nullable=False),
        sa.Column("fiscal_period", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
        sa.Column("report_date", sa.Date(), nullable=False),
        sa.Column("publish_date", sa.Date(), nullable=False),
        sa.Column("restated_date", sa.Date(), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("composite_key", name="uq_income_statement_composite_key"),
    )
    op.create_index(
        op.f("ix_income_statement_composite_key"),
        "income_statement",
        ["composite_key"],
        unique=False,
    )
    op.create_index(
        op.f("ix_income_statement_ticker"),
        "income_statement",
        ["ticker"],
        unique=False,
    )
    op.create_index(
        op.f("ix_income_statement_simfin_id"),
        "income_statement",
        ["simfin_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_income_statement_simfin_id"), table_name="income_statement")
    op.drop_index(op.f("ix_income_statement_ticker"), table_name="income_statement")
    op.drop_index(
        op.f("ix_income_statement_composite_key"),
        table_name="income_statement",
    )
    op.drop_table("income_statement")

    op.drop_index(
        op.f("ix_cash_flow_statement_simfin_id"),
        table_name="cash_flow_statement",
    )
    op.drop_index(
        op.f("ix_cash_flow_statement_ticker"),
        table_name="cash_flow_statement",
    )
    op.drop_index(
        op.f("ix_cash_flow_statement_composite_key"),
        table_name="cash_flow_statement",
    )
    op.drop_table("cash_flow_statement")

    op.drop_index(op.f("ix_balance_sheet_simfin_id"), table_name="balance_sheet")
    op.drop_index(op.f("ix_balance_sheet_ticker"), table_name="balance_sheet")
    op.drop_index(op.f("ix_balance_sheet_composite_key"), table_name="balance_sheet")
    op.drop_table("balance_sheet")
