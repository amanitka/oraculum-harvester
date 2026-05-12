"""Add derived metrics table

Revision ID: 0002_add_derived_table
Revises: 0001_initial
Create Date: 2026-05-12 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel

revision: str = "0002_add_derived_table"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "t_derived",
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
        sa.Column("ebitda", sa.Float(), nullable=True),
        sa.Column("free_cash_flow", sa.Float(), nullable=True),
        sa.Column("ncav", sa.Float(), nullable=True),
        sa.Column("net_net_working_capital", sa.Float(), nullable=True),
        sa.Column("shares_stabilized", sa.Float(), nullable=True),
        sa.Column("return_on_equity", sa.Float(), nullable=True),
        sa.Column("net_margin", sa.Float(), nullable=True),
        sa.Column("revenue", sa.Float(), nullable=True),
        sa.Column("net_income", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("composite_key", name="uq_derived_composite_key"),
    )
    op.create_index(
        op.f("ix_t_derived_composite_key"),
        "t_derived",
        ["composite_key"],
        unique=False,
    )
    op.create_index(op.f("ix_t_derived_ticker"), "t_derived", ["ticker"], unique=False)
    op.create_index(
        op.f("ix_t_derived_simfin_id"),
        "t_derived",
        ["simfin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_t_derived_variant"),
        "t_derived",
        ["variant"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("t_derived")
