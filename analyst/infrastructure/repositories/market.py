from sqlmodel import select
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert

from analyst.infrastructure.models.market import MarketDB
from common.domain.market import Market


class MarketRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_batch(self, markets: list[Market]) -> None:
        if not markets:
            return

        stmt = insert(MarketDB).values(
            [
                {
                    "market_id": m.market_id,
                    "market_name": m.market_name,
                    "currency": m.currency,
                    "extracted_at": m.extracted_at,
                }
                for m in markets
            ]
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["market_id"],
            set_=dict(
                market_name=stmt.excluded.market_name,
                currency=stmt.excluded.currency,
                extracted_at=stmt.excluded.extracted_at,
            ),
        )

        self._session.execute(stmt)
