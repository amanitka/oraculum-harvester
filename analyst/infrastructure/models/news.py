"""
SQLModel definitions for news and sentiment data.
"""
from __future__ import annotations

from datetime import datetime
from typing import List, Optional, Any

from sqlmodel import Field, SQLModel
from sqlalchemy import Column, Index, PrimaryKeyConstraint, String, TIMESTAMP, TEXT, JSON
from sqlalchemy.dialects.postgresql import REAL

from analyst.infrastructure.models.base import AuditMixin


class News(AuditMixin, SQLModel, table=True):  # type: ignore[call-arg,misc]
    __tablename__ = 't_news'

    id: str = Field(sa_column=Column(String(64), nullable=False, comment="SHA256 hash"))
    title: str = Field(sa_column=Column(TEXT, nullable=False))
    url: str = Field(sa_column=Column(TEXT, nullable=False))
    time_published: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    authors: Optional[List[str]] = Field(default=None, sa_column=Column(JSON))
    summary: str = Field(sa_column=Column(TEXT, nullable=False))
    source: Optional[str] = Field(default=None, max_length=255)
    category_within_source: Optional[str] = Field(default=None, max_length=255)
    source_domain: Optional[str] = Field(default=None, max_length=255)
    topics: Optional[List[Any]] = Field(default=None, sa_column=Column(JSON))
    overall_sentiment_score: Optional[float] = Field(default=None, sa_column=Column(REAL))
    overall_sentiment_label: Optional[str] = Field(default=None, max_length=50)
    extracted_at: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    sentiment_score_definition: Optional[str] = Field(default=None, sa_column=Column(TEXT))
    relevance_score_definition: Optional[str] = Field(default=None, sa_column=Column(TEXT))

    __table_args__ = (
        PrimaryKeyConstraint('id', 'time_published'),
        Index('ix_news_time_published', 'time_published'),
        {
            'postgresql_partition_by': 'RANGE (time_published)',
        }
    )


class NewsTicker(AuditMixin, SQLModel, table=True):  # type: ignore[call-arg,misc]
    __tablename__ = 't_news_ticker'

    news_id: str = Field(sa_column=Column(String(64), nullable=False))
    time_published: datetime = Field(sa_column=Column(TIMESTAMP(timezone=True), nullable=False))
    ticker: str = Field(max_length=16)
    relevance_score: Optional[float] = Field(default=None, sa_column=Column(REAL))
    ticker_sentiment_score: Optional[float] = Field(default=None, sa_column=Column(REAL))
    ticker_sentiment_label: Optional[str] = Field(default=None, max_length=50)

    __table_args__ = (
        PrimaryKeyConstraint('news_id', 'ticker', 'time_published'),
        Index('ix_news_ticker_ticker', 'ticker'),
        {
            'postgresql_partition_by': 'RANGE (time_published)',
        }
    )
