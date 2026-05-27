from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from analyst.infrastructure.models.industry import IndustryDB
from common.domain.industry import Industry


class IndustryRepository:
    def __init__(self, session: Session):
        self._session = session

    def upsert_batch(self, industries: list[Industry]) -> None:
        if not industries:
            return

        stmt = insert(IndustryDB).values(
            [
                {
                    "industry_id": ind.industry_id,
                    "sector_name": ind.sector_name,
                    "industry_name": ind.industry_name,
                    "statement_template": ind.statement_template,
                    "extracted_at": ind.extracted_at,
                }
                for ind in industries
            ]
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=["industry_id"],
            set_=dict(
                sector_name=stmt.excluded.sector_name,
                industry_name=stmt.excluded.industry_name,
                statement_template=stmt.excluded.statement_template,
                extracted_at=stmt.excluded.extracted_at,
            ),
        )

        self._session.execute(stmt)
