import logging
from uuid import UUID

from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.app import broker
from analyst.dependencies import Session as DependsSession
from analyst.infrastructure.repositories.market import MarketRepository
from common.config import config
from common.domain.market import Market

logger = logging.getLogger(__name__)


@broker.subscriber(
    config.topics.market,
    group_id=config.analyst_consumer_group,
    auto_offset_reset="earliest",
)
async def on_market(market: Market, session: AsyncSession = DependsSession()) -> None:
    logger.info(f"Received market data for {market.market_id}")
    
    # We use the injected async session. However, the repository might be synchronous.
    # Since we defined MarketRepository to take a sync Session, but our dependency injection
    # gives us an AsyncSession, we need to handle this correctly.
    # To avoid rewriting the entire repo to async right now, we can use run_sync.
    
    def _upsert(sync_session):
        repo = MarketRepository(sync_session)
        repo.upsert_batch([market])
        
    await session.run_sync(_upsert)
    await session.commit()
