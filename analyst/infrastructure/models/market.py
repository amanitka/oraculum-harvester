from datetime import datetime
from typing import Optional

from sqlmodel import Field, SQLModel


class MarketDB(SQLModel, table=True):
    """
    Represents a row in the `t_market` table.
    """

    __tablename__ = "t_market"

    market_id: str = Field(primary_key=True)
    market_name: str
    currency: Optional[str] = None
    extracted_at: datetime
