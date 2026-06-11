"""Typed publishers for every harvester output topic.

Exposing them as module-level attributes keeps service code declarative
and gives FastStream the Pydantic schemas it needs for AsyncAPI docs
(`faststream docs gen harvester.app:app`).
"""

from __future__ import annotations
from typing import List

from common.config import config
from common.domain import (
    DataFileReadyEvent,
    NewsArticle,
)
from harvester.app import broker

news_articles = broker.publisher(config.topics.news, schema=List[NewsArticle])
data_file_ready = broker.publisher(config.topics.data_file_ready, schema=DataFileReadyEvent)
