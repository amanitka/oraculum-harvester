from typing import Generator
from sqlmodel import create_engine, Session, select
from datetime import datetime, timezone

from common.config import config
from analyst.models import TickerDB
from common.domain.ticker import Ticker

engine = create_engine(config.database_url, echo=False)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session


def upsert_ticker(session: Session, ticker: Ticker) -> TickerDB:
    statement = select(TickerDB).where(
        TickerDB.symbol == ticker.symbol, TickerDB.market == ticker.market
    )
    existing_ticker = session.exec(statement).first()

    if existing_ticker:
        # Update fields
        update_data = ticker.model_dump(exclude_unset=True)
        # We don't want to update created_at or id
        for key, value in update_data.items():
            if hasattr(existing_ticker, key):
                setattr(existing_ticker, key, value)
        existing_ticker.updated_at = datetime.now(timezone.utc)
        session.add(existing_ticker)
        db_obj = existing_ticker
    else:
        # Insert
        db_obj = TickerDB(**ticker.model_dump())
        session.add(db_obj)

    session.commit()
    session.refresh(db_obj)
    return db_obj  # type: ignore[no-any-return]
