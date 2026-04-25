"""Create t_share_price partitioned table.

Revision ID: f3e2d1c0b9a8
Revises: 9b3e2f7c1a6d
Create Date: 2026-04-25
"""

from __future__ import annotations

from alembic import op
from sqlalchemy import text

revision = "f3e2d1c0b9a8"
down_revision = "9b3e2f7c1a6d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Create the range-partitioned ``t_share_price`` table and its indexes."""
    op.execute(
        text(
            """
            CREATE TABLE t_share_price (
                ticker             VARCHAR      NOT NULL,
                sim_fin_id         INTEGER,
                currency           VARCHAR(10),
                market             VARCHAR(20)  NOT NULL,
                trade_date         DATE         NOT NULL,
                open               NUMERIC(18, 4),
                high               NUMERIC(18, 4),
                low                NUMERIC(18, 4),
                close              NUMERIC(18, 4),
                adj_close          NUMERIC(18, 4),
                volume             BIGINT,
                shares_outstanding BIGINT,
                dividend           NUMERIC(18, 6),
                extracted_at       TIMESTAMPTZ  NOT NULL,
                CONSTRAINT pk_share_price PRIMARY KEY (ticker, market, trade_date)
            ) PARTITION BY RANGE (trade_date)
            """
        )
    )
    op.execute(
        text(
            "CREATE INDEX ix_share_price_market_trade_date"
            " ON t_share_price (market, trade_date)"
        )
    )
    op.execute(
        text(
            "CREATE INDEX ix_share_price_ticker"
            " ON t_share_price (ticker)"
        )
    )


def downgrade() -> None:
    """Drop the ``t_share_price`` table and all its partitions."""
    op.execute(text("DROP TABLE IF EXISTS t_share_price CASCADE"))
