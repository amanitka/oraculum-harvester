"""
Kafka subscriber for news and sentiment data.
"""

from __future__ import annotations

import logging
from typing import List

from faststream.kafka import KafkaMessage

from analyst.app import broker
from analyst.infrastructure.engine import EngineProvider
from analyst.infrastructure.news_repository import NewsRepository
from common.config import config
from common.domain.news import NewsArticle

logger = logging.getLogger(__name__)


@broker.subscriber(config.topics.news)
async def handle_news_batch(articles: List[NewsArticle], msg: KafkaMessage) -> None:
    """Consumes a batch of enriched news articles and loads them into the database."""
    if not articles:
        return

    logger.info("Received news batch with %d articles.", len(articles))

    factory = await EngineProvider.session_factory()
    async with factory() as session:
        repository = NewsRepository(session)
        await repository.batch_upsert_news(articles)
        await session.commit()
