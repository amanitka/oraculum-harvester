"""Domain models for SEC 13F Form data."""

from __future__ import annotations

from datetime import date
from typing import Optional

from pydantic import BaseModel


class Sec13FHolding(BaseModel):
    """Single 13F position row extracted from INFOTABLE XML or TSV."""

    accession_number: str
    cik: str
    manager_name: str
    period_of_report: date
    filing_date: date
    issuer_name: str
    class_title: str
    cusip: str
    value_usd: int
    shares_or_prn_amount: int
    shares_or_prn_type: str
    option_type: Optional[str] = None
    investment_discretion: str
    voting_auth_sole: int = 0
    voting_auth_shared: int = 0
    voting_auth_none: int = 0


class Sec13FFiler(BaseModel):
    """13F institutional filer from the quarterly master index."""

    cik: str
    manager_name: str
    form_type: str
    filing_date: date
    accession_number: str
    year: int
    quarter: int
