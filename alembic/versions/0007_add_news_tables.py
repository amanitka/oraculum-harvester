"""add_news_tables

Revision ID: 0007
Revises: 0006_daily_market_signals
Create Date: 2024-05-24 10:00:00.000000

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "0007"
down_revision = "0006_daily_market_signals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # t_news
    op.create_table(
        "t_news",
        sa.Column("id", sa.String(length=64), nullable=False, comment="SHA256 hash"),
        sa.Column("title", sa.Text(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("time_published", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("authors", sa.JSON(), nullable=True),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("source", sa.String(length=255), nullable=True),
        sa.Column("category_within_source", sa.String(length=255), nullable=True),
        sa.Column("source_domain", sa.String(length=255), nullable=True),
        sa.Column("topics", sa.JSON(), nullable=True),
        sa.Column("overall_sentiment_score", sa.REAL(), nullable=True),
        sa.Column("overall_sentiment_label", sa.String(length=50), nullable=True),
        sa.Column("extracted_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("sentiment_score_definition", sa.Text(), nullable=True),
        sa.Column("relevance_score_definition", sa.Text(), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", "time_published"),
        postgresql_partition_by="RANGE (time_published)",
    )
    op.create_index("ix_news_time_published", "t_news", ["time_published"], unique=False)

    # t_news_ticker
    op.create_table(
        "t_news_ticker",
        sa.Column("news_id", sa.String(length=64), nullable=False),
        sa.Column("time_published", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("relevance_score", sa.REAL(), nullable=True),
        sa.Column("ticker_sentiment_score", sa.REAL(), nullable=True),
        sa.Column("ticker_sentiment_label", sa.String(length=50), nullable=True),
        sa.Column("created_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("updated_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["news_id", "time_published"], ["t_news.id", "t_news.time_published"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("news_id", "ticker", "time_published"),
        postgresql_partition_by="RANGE (time_published)",
    )
    op.create_index("ix_news_ticker_ticker", "t_news_ticker", ["ticker"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_news_ticker_ticker", table_name="t_news_ticker")
    op.drop_table("t_news_ticker")
    op.drop_index("ix_news_time_published", table_name="t_news")
    op.drop_table("t_news")
