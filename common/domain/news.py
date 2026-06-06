from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field


class NewsTickerSentiment(BaseModel):
    ticker: str
    relevance_score: float
    ticker_sentiment_score: float
    ticker_sentiment_label: str


class TopicRelevance(BaseModel):
    topic: str
    relevance_score: float


class NewsArticle(BaseModel):
    id: str = Field(..., description="SHA256 hash of key fields for idempotency.")
    title: str
    url: str
    time_published: str
    authors: List[str]
    summary: str
    banner_image: Optional[str] = None
    source: str
    category_within_source: str
    source_domain: str
    topics: List[TopicRelevance]
    overall_sentiment_score: float
    overall_sentiment_label: str
    ticker_sentiment: List[NewsTickerSentiment]
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    # Denormalized from the feed for data lineage
    sentiment_score_definition: str
    relevance_score_definition: str


class NewsFeed(BaseModel):
    items: str
    sentiment_score_definition: str
    relevance_score_definition: str
    feed: List[NewsArticle]
