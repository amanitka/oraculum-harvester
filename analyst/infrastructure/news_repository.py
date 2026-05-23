"""
Repository for persisting news and sentiment data.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Dict, Any
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from analyst.infrastructure.models import News, NewsTicker

if TYPE_CHECKING:
    from common.domain.news import NewsArticle

logger = logging.getLogger(__name__)


class NewsRepository:
    """Handles database operations for news data."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_max_time_published(self) -> datetime | None:
        """Returns the latest time_published from the database, or None if empty."""
        stmt = select(func.max(News.time_published))
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def batch_upsert_news(self, articles: List[NewsArticle]) -> None:
        """
        Performs a batch UPSERT of news articles and their associated ticker sentiments.
        """
        if not articles:
            return

        news_values = [self._article_to_news_dict(article) for article in articles]
        ticker_values = [
            self._article_to_ticker_dict(article, sentiment)
            for article in articles
            for sentiment in article.ticker_sentiment
        ]

        # Upsert into t_news
        news_stmt = insert(News).values(news_values)
        news_stmt = news_stmt.on_conflict_do_update(
            index_elements=["id", "time_published"],
            set_={
                "title": news_stmt.excluded.title,
                "url": news_stmt.excluded.url,
                "summary": news_stmt.excluded.summary,
                "authors": news_stmt.excluded.authors,
                "topics": news_stmt.excluded.topics,
                "overall_sentiment_score": news_stmt.excluded.overall_sentiment_score,
                "overall_sentiment_label": news_stmt.excluded.overall_sentiment_label,
                "extracted_at": news_stmt.excluded.extracted_at,
                "sentiment_score_definition": news_stmt.excluded.sentiment_score_definition,
                "relevance_score_definition": news_stmt.excluded.relevance_score_definition,
            },
        )
        await self._session.execute(news_stmt)

        # Upsert into t_news_ticker
        if ticker_values:
            ticker_stmt = insert(NewsTicker).values(ticker_values)
            ticker_stmt = ticker_stmt.on_conflict_do_update(
                index_elements=["news_id", "ticker", "time_published"],
                set_={
                    "relevance_score": ticker_stmt.excluded.relevance_score,
                    "ticker_sentiment_score": ticker_stmt.excluded.ticker_sentiment_score,
                    "ticker_sentiment_label": ticker_stmt.excluded.ticker_sentiment_label,
                },
            )
            await self._session.execute(ticker_stmt)

        logger.info("Upserted %d news articles and %d ticker sentiments.", len(news_values), len(ticker_values))

    @staticmethod
    def _article_to_news_dict(article: NewsArticle) -> Dict[str, Any]:
        """Converts a NewsArticle domain model to a dictionary for the News table."""
        return {
            "id": article.id,
            "title": article.title,
            "url": article.url,
            "time_published": article.time_published,
            "authors": [author for author in article.authors],
            "summary": article.summary,
            "source": article.source,
            "category_within_source": article.category_within_source,
            "source_domain": article.source_domain,
            "topics": [topic.model_dump() for topic in article.topics],
            "overall_sentiment_score": article.overall_sentiment_score,
            "overall_sentiment_label": article.overall_sentiment_label,
            "extracted_at": article.extracted_at,
            "sentiment_score_definition": article.sentiment_score_definition,
            "relevance_score_definition": article.relevance_score_definition,
        }

    @staticmethod
    def _article_to_ticker_dict(article: NewsArticle, sentiment) -> Dict[str, Any]:
        """Converts a NewsArticle and a sentiment to a dictionary for the NewsTicker table."""
        return {
            "news_id": article.id,
            "time_published": article.time_published,
            "ticker": sentiment.ticker,
            "relevance_score": sentiment.relevance_score,
            "ticker_sentiment_score": sentiment.ticker_sentiment_score,
            "ticker_sentiment_label": sentiment.ticker_sentiment_label,
        }
