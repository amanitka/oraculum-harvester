from datetime import datetime

from sqlmodel import Field, SQLModel


class IndustryDB(SQLModel, table=True):
    """
    Represents a row in the `t_industry` table.
    """

    __tablename__ = "t_industry"

    industry_id: str = Field(primary_key=True)
    sector_name: str
    industry_name: str
    statement_template: str = Field(
        default="general", 
        description="The mapped SimFin statement template for this industry."
    )
    extracted_at: datetime
