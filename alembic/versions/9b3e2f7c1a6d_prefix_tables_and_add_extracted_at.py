"""prefix_tables_and_add_extracted_at

Revision ID: 9b3e2f7c1a6d
Revises: d4a1b6e4f2c1
Create Date: 2026-04-25 11:20:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "9b3e2f7c1a6d"
down_revision: Union[str, Sequence[str], None] = "d4a1b6e4f2c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _add_extracted_at(table_name: str) -> None:
    op.add_column(
        table_name,
        sa.Column("extracted_at", sa.DateTime(), nullable=True),
    )
    op.execute(
        sa.text(
            f"UPDATE {table_name} "
            "SET extracted_at = created_at "
            "WHERE extracted_at IS NULL"
        )
    )
    op.alter_column(table_name, "extracted_at", nullable=False)


def upgrade() -> None:
    """Upgrade schema."""
    op.rename_table("ticker", "t_ticker")
    op.rename_table("balance_sheet", "t_balance_sheet")
    op.rename_table("cash_flow_statement", "t_cash_flow_statement")
    op.rename_table("income_statement", "t_income_statement")

    _add_extracted_at("t_balance_sheet")
    _add_extracted_at("t_cash_flow_statement")
    _add_extracted_at("t_income_statement")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("t_income_statement", "extracted_at")
    op.drop_column("t_cash_flow_statement", "extracted_at")
    op.drop_column("t_balance_sheet", "extracted_at")

    op.rename_table("t_income_statement", "income_statement")
    op.rename_table("t_cash_flow_statement", "cash_flow_statement")
    op.rename_table("t_balance_sheet", "balance_sheet")
    op.rename_table("t_ticker", "ticker")
