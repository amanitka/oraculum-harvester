"""
Service layer for fetching and publishing news and sentiment data.
"""

from __future__ import annotations

import hashlib
import logging
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from common.domain.news import NewsArticle

if TYPE_CHECKING:
    from harvester.providers.alphavantage_provider import AlphaVantageProvider

logger = logging.getLogger(__name__)

NEWS_PUBLISH_BATCH_SIZE = 200


class NewsService:
    """Orchestrates fetching, transforming, and publishing news data."""

    def __init__(self, provider: AlphaVantageProvider, publisher: Any) -> None:
        self._provider = provider
        self._publisher = publisher

    async def refresh_news(self, time_from: Optional[str] = None, time_to: Optional[str] = None) -> int:
        """
        Fetches news from the provider, transforms it, and publishes it to Kafka
        in batches to avoid message size limits.

        Args:
            time_from: The start time for the news query (YYYYMMDDTHHMM).
            time_to: The end time for the news query (YYYYMMDDTHHMM).

        Returns:
            The number of news articles published.
        """
        logger.info("Starting news data refresh...")
        # The provider's method is synchronous, so we don't await it.
        raw_data = self._provider.fetch_news_sentiment(time_from=time_from, time_to=time_to)

        if not raw_data or not raw_data.get("feed"):
            logger.warning("No news data received from provider.")
            return 0

        enriched_articles = self._enrich_and_validate(raw_data)
        article_count = len(enriched_articles)

        if not enriched_articles:
            logger.info("No articles to publish after enrichment.")
            return 0

        logger.info("Publishing %d articles in batches of %d...", article_count, NEWS_PUBLISH_BATCH_SIZE)
        for i in range(0, article_count, NEWS_PUBLISH_BATCH_SIZE):
            batch = enriched_articles[i: i + NEWS_PUBLISH_BATCH_SIZE]
            await self._publisher.publish(batch)
            logger.debug("Published batch of %d articles.", len(batch))

        logger.info("Successfully published %d news articles.", article_count)
        return article_count

    def _enrich_and_validate(self, raw_data: Dict[str, Any]) -> List[NewsArticle]:
        """
        Enriches raw article data with a unique ID and denormalized metadata,
        then validates the result against the NewsArticle Pydantic model.
        """
        sentiment_def = raw_data.get("sentiment_score_definition", "")
        relevance_def = raw_data.get("relevance_score_definition", "")
        raw_feed = raw_data.get("feed", [])

        enriched = []
        for raw_article in raw_feed:
            # Denormalize metadata for data lineage
            raw_article["sentiment_score_definition"] = sentiment_def
            raw_article["relevance_score_definition"] = relevance_def

            # Generate a deterministic, unique ID for idempotency
            raw_article["id"] = self._generate_article_id(raw_article)

            # Now validate against the strict Pydantic model
            try:
                article = NewsArticle.model_validate(raw_article)
                enriched.append(article)
            except Exception as e:
                logger.error(f"Failed to validate article {raw_article.get('title')}: {e}")

        return enriched

    @staticmethod
    def _generate_article_id(raw_article: Dict[str, Any]) -> str:
        """
        Creates a SHA256 hash from key article fields to serve as a unique ID.
        """
        # Using a tuple of key fields to create a stable hash
        # URL is a strong candidate for uniqueness, but combining with time and title adds robustness.
        key_tuple = (
            raw_article.get("url", ""),
            raw_article.get("time_published", ""),
            raw_article.get("title", ""),
        )
        # Encode the tuple to a byte string before hashing
        encoded_key = str(key_tuple).encode("utf-8")
        return hashlib.sha256(encoded_key).hexdigest()
