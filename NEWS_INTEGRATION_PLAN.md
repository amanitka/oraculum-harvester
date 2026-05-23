# News and Sentiment Data Integration Plan

This document outlines the step-by-step process for integrating the Alpha Vantage news and sentiment data feed into the Oraculum platform.

## 1. High-Level Design

The integration will follow the existing layered architecture, introducing a new data pipeline from the `harvester` service to the `analyst` service via Kafka.

- **Harvester Service**:
    1.  A new provider, `alphavantage_provider.py`, will fetch news data.
    2.  A dedicated service method will orchestrate the fetching, transformation, and publishing.
    3.  Data will be transformed into standardized Pydantic DTOs. The metadata (`sentiment_score_definition`, `relevance_score_definition`) will be denormalized and copied into each news article record.
    4.  A batch of news articles will be published as a single Kafka message.
- **Analyst Service**:
    1.  A new Kafka consumer will subscribe to the news topic.
    2.  A data loader will parse the message and perform a batch `UPSERT` into the new database tables.
    3.  **On startup, the analyst service will automatically create the required yearly partitions for the current and next year.**
- **Database**:
    1.  Two new tables will be created: `t_news` and `t_news_ticker`.
    2.  Both tables will be partitioned by year based on `time_published` for efficient data management and cleanup. Data retention policy is 2 years.
    3.  **A new Alembic migration script will be created to manage the schema evolution.**

## 2. Implementation Steps

### Step 2.1: Domain Models (common)

Define the Pydantic models for the news data payload.

- **File**: `common/domain/news.py` (new file)
- **Models**:
    - `NewsArticle`: Represents a single news item, including the denormalized score definitions for data lineage.
    - `NewsTickerSentiment`: Represents the sentiment for a specific ticker within an article.
    - `NewsFeed`: The top-level object mirroring the API response.

```python
# common/domain/news.py

from datetime import datetime
from typing import List, Optional, Any
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
```

### Step 2.2: Database Schema & Migrations (analyst & root)

Define the table structures in a new SQLAlchemy model file and create the corresponding Alembic migration.

- **Model File**: `analyst/infrastructure/models/news.py` (new file)
- **Migration File**: `alembic/versions/0007_add_news_tables.py` (new file)
- **Tables**:
    - `t_news`: Stores the main article content, including the score definitions. Partitioned by `time_published`.
    - `t_news_ticker`: Stores ticker-specific sentiment. Partitioned by `time_published`.

### Step 2.3: Automatic Partition Management (analyst)

Extend the existing `PartitionManager` to automatically create yearly partitions for `t_news` and `t_news_ticker` on application startup.

- **File**: `analyst/infrastructure/partition_manager.py` (updated)
- **Logic**:
    - Create a new method `ensure_news_partitions`.
    - This method will be called during the analyst service's startup sequence.
    - It will check for and create partitions for the current year and one year ahead (`years_ahead=1`) for both `t_news` and `t_news_ticker`.
    - This follows the same pattern as the existing `ensure_share_price_partitions`, ensuring a unified approach to partition management.
    - A `DEFAULT` partition will not be used; it is better to let an insert fail on a missing partition to highlight data quality issues than to have it silently succeed into a catch-all partition.

### Step 2.4: Harvester Implementation

1.  **Provider (`harvester/providers/alphavantage_provider.py`)**:
    - Finalize the `fetch_news_sentiment` method.

2.  **Service (`harvester/services/news_service.py`)** (new file):
    - Implement a `refresh_news` method that:
        - Fetches raw data from the provider.
        - Validates it into a `NewsFeed` Pydantic model.
        - **Iterates through each article in `NewsFeed.feed`, copying the top-level `sentiment_score_definition` and `relevance_score_definition` into each article object.**
        - Computes the SHA256 `id` for each article.
        - Publishes the list of enriched `NewsArticle` objects to Kafka.

3.  **Publisher (`harvester/publishers.py`)**:
    - Add a method to publish the list of `NewsArticle` models to the `oraculum.news.v1` topic.

### Step 2.5: Analyst Implementation

1.  **Consumer (`analyst/subscribers/news_subscriber.py`)** (new file):
    - Listens to `oraculum.news.v1`.
    - Validates the incoming message (a list of articles) and passes it to the repository.

2.  **Repository (`analyst/infrastructure/news_repository.py`)** (new file):
    - Implement a `batch_upsert_news` method that takes a list of `NewsArticle` objects.
    - The logic handles a batch `UPSERT` into two tables:
        1.  `t_news`
        2.  `t_news_ticker` (extracting from the nested `ticker_sentiment` list in each article).
    - The entire operation must be in a single transaction.

## 3. Data Retention and Cleanup

-   **Policy**: 2 years of rolling data.
-   **Mechanism**: A scheduled job will drop partitions older than 2 years from both `t_news` and `t_news_ticker`. This is an efficient, near-instantaneous operation.
