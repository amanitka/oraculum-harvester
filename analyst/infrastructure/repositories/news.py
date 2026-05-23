"""
Repository for persisting news and sentiment data.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta
from typing import TYPE_CHECKING, Any, Dict, List

from sqlalchemy import func, select
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

    async def fetch_recent_news_for_ticker(self, ticker: str, days_back: int = 30) -> List[Dict[str, Any]]:
        """
        Fetches recent news and ticker sentiments as separate lists and joins them in code.
        """
        from_date = datetime.now(timezone.utc) - timedelta(days=days_back)

        # 1. Fetch all relevant ticker sentiment data
        ticker_stmt = (
            select(NewsTicker)
            .where(NewsTicker.ticker == ticker)
            .where(NewsTicker.time_published >= from_date)
        )
        ticker_results = await self._session.execute(ticker_stmt)
        sentiments = ticker_results.scalars().all()

        if not sentiments:
            return []

        # 2. Get the unique news IDs from the sentiment data
        news_ids = {s.news_id for s in sentiments}

        # 3. Fetch the corresponding news articles
        news_stmt = select(News).where(News.id.in_(news_ids))
        news_results = await self._session.execute(news_stmt)
        news_map = {n.id: n for n in news_results.scalars().all()}

        # 4. Join the data in Python
        joined_data = []
        for sentiment in sentiments:
            news_article = news_map.get(sentiment.news_id)
            if news_article:
                joined_data.append(
                    {
                        "article": news_article,
                        "sentiment": sentiment,
                    }
                )
        
        # Sort by publication date descending
        joined_data.sort(key=lambda x: x["article"].time_published, reverse=True)

        return joined_data

    async def batch_upsert_news(self, articles: List[NewsArticle]) -> None:
        """
        Performs a batch UPSERT of news articles and their associated ticker sentiments.
        This method de-duplicates ticker sentiment data within the batch to prevent
        cardinality violations on composite primary keys.
        """
        if not articles:
            return

        now = datetime.now(timezone.utc)

        # Prepare news data, adding the update timestamp
        news_values = []
        for article in articles:
            # Exclude fields that are not in the t_news table
            payload = article.model_dump(exclude={"ticker_sentiment", "banner_image"})
            payload["updated_at"] = now
            news_values.append(payload)

        # Prepare and de-duplicate ticker sentiment data
        unique_ticker_sentiments: Dict[tuple[str, str], Dict[str, Any]] = {}
        for article in articles:
            for sentiment in article.ticker_sentiment:
                key = (article.id, sentiment.ticker)
                if key not in unique_ticker_sentiments:
                    payload = sentiment.model_dump()
                    payload["news_id"] = article.id
                    payload["time_published"] = article.time_published
                    payload["updated_at"] = now
                    unique_ticker_sentiments[key] = payload

        ticker_values = list(unique_ticker_sentiments.values())

        # Upsert into t_news
        if news_values:
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
                    "updated_at": news_stmt.excluded.updated_at,
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
                    "updated_at": ticker_stmt.excluded.updated_at,
                },
            )
            await self._session.execute(ticker_stmt)

        logger.info("Upserted %d news articles and %d ticker sentiments.", len(news_values), len(ticker_values))
