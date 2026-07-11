from typing import Literal, List, Optional
from datetime import date
from pydantic import BaseModel
from common.requests.base import Request

class DocumentTypeRequest(BaseModel):
    document_type: str
    last_processed_file_date: Optional[date] = None

class TickerDocumentItem(BaseModel):
    ticker: str
    market: str = "US"
    document_types: List[DocumentTypeRequest]

class FetchSecDocumentsRequest(Request):
    """Command to fetch SEC documents (8-K, 10-K, etc.) for specific companies."""
    
    request_type: Literal["fetch_sec_documents"] = "fetch_sec_documents"
    items: List[TickerDocumentItem]
