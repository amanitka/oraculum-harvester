"""Fix share price volume types

Revision ID: 0003_fix_share_price_types
Revises: 0002_create_derived_metrics_view
Create Date: 2026-05-15 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = "0003_fix_share_price_types"
down_revision: Union[str, Sequence[str], None] = "0002_create_derived_metrics_view"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Use BigInteger for volume and shares_outstanding as they can exceed 2.1B (Postgres INT max)
    op.alter_column("t_share_price", "volume", type_=sa.BigInteger())
    op.alter_column("t_share_price", "shares_outstanding", type_=sa.BigInteger())


def downgrade() -> None:
    # Technically dropping down could result in data loss if values > 2B
    op.alter_column("t_share_price", "volume", type_=sa.Integer())
    op.alter_column("t_share_price", "shares_outstanding", type_=sa.Integer())
