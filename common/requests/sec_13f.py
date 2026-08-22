"""Requests for SEC 13F Form ingestion."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from common.requests.base import Request


class Fetch13FBulkRequest(Request):
    """Request to download the quarterly SEC 13F bulk zip."""
    
    request_type: Literal["fetch_13f_bulk"] = "fetch_13f_bulk"
    year: int
    quarter: int = Field(ge=1, le=4)


class Fetch13FCikRequest(Request):
    """Request to download the latest 13F filing for a specific CIK."""
    
    request_type: Literal["fetch_13f_cik"] = "fetch_13f_cik"
    cik: str = Field(min_length=1, max_length=10, description="SEC CIK, zero-padded to 10 digits")


class Fetch13FFilersRequest(Request):
    """Request to download the quarterly SEC master index and extract 13F filers."""
    
    request_type: Literal["fetch_13f_filers"] = "fetch_13f_filers"
    year: int
    quarter: int = Field(ge=1, le=4)
