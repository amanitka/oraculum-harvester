"""Rename payload to statement_data

Revision ID: 0008_rename_payload_to_statement_data
Revises: 0007_add_news_tables
Create Date: 2026-05-01 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

# revision identifiers, used by Alembic.
revision: str = "0008_rename_payload_to_statement_data"
down_revision: Union[str, Sequence[str], None] = "0007_add_news_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.alter_column("t_balance_sheet", "payload", new_column_name="statement_data", existing_type=JSONB)
    op.alter_column("t_cash_flow_statement", "payload", new_column_name="statement_data", existing_type=JSONB)
    op.alter_column("t_income_statement", "payload", new_column_name="statement_data", existing_type=JSONB)


def downgrade() -> None:
    """Downgrade schema."""
    op.alter_column("t_balance_sheet", "statement_data", new_column_name="payload", existing_type=JSONB)
    op.alter_column("t_cash_flow_statement", "statement_data", new_column_name="payload", existing_type=JSONB)
    op.alter_column("t_income_statement", "statement_data", new_column_name="payload", existing_type=JSONB)
