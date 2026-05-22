import logging
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session as DependsSession
from analyst.infrastructure.repositories.industry import IndustryRepository
from common.config import config
from common.domain.industry import Industry

logger = logging.getLogger(__name__)


@broker.subscriber(
    config.topics.industry,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_industry(industry: Industry, session: AsyncSession = DependsSession()) -> None:
    logger.info(f"Received industry data for {industry.industry_id}")

    def _upsert(sync_session):
        repo = IndustryRepository(sync_session)
        repo.upsert_batch([industry])

    await session.run_sync(_upsert)
    await session.commit()
