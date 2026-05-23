"""
APScheduler jobs for the harvester news service.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from apscheduler.schedulers.asyncio import AsyncIOScheduler

if TYPE_CHECKING:
    from harvester.services.news_service import NewsService

logger = logging.getLogger(__name__)


def create_news_refresh_scheduler(service: NewsService) -> AsyncIOScheduler:
    """Creates an APScheduler to periodically refresh news data."""
    scheduler = AsyncIOScheduler()
    # Run once every 4 hours, as per the plan
    scheduler.add_job(
        service.refresh_news,
        "interval",
        hours=4,
        id="refresh_news_data",
        replace_existing=True,
    )
    return scheduler
