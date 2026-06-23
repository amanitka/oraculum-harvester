"""OpenInsider data provider."""

import hashlib
import logging
import time
from datetime import datetime, timezone
from typing import Any, Dict, Iterator, Optional
from urllib.parse import urlencode, urlparse

import pandas as pd

from common.config import config
from common.domain.insider_transaction import InsiderTransaction

logger = logging.getLogger(__name__)


class OpenInsiderProvider:
    """Fetches insider transactions from OpenInsider."""

    def __init__(self) -> None:
        self.base_url = config.openinsider_base_url
        self.records_per_page = config.openinsider_records_per_page
        self.delay_seconds = config.openinsider_delay_seconds
        self.default_params = config.openinsider_default_params

    def _build_url(self, page: int) -> str:
        params = self.default_params.copy()
        params.update({
            "cnt": self.records_per_page,
            "page": page,
        })
        parsed = urlparse(self.base_url)
        return parsed._replace(query=urlencode(params)).geturl()

    def fetch_transactions(self, max_filing_date: Optional[datetime] = None) -> Iterator[InsiderTransaction]:
        """Yield validated `InsiderTransaction` records until max_filing_date is reached."""
        page = 1
        extracted_at = datetime.now(timezone.utc)
        
        while True:
            url = self._build_url(page)
            logger.info("Fetching OpenInsider page %d", page)
            
            try:
                tables = pd.read_html(url)
            except Exception as exc:
                logger.error("Failed to read HTML from %s: %s", url, exc)
                break
                
            # Find the correct data table. Usually the largest one or one with specific columns.
            df = None
            for tbl in reversed(tables):
                if hasattr(tbl.columns, "str"):
                    # Normalize \xa0 to regular spaces to make exact matching reliable
                    tbl.columns = tbl.columns.str.replace(r'\xa0', ' ', regex=True).str.strip()
                    
                if "Ticker" in tbl.columns and "Insider Name" in tbl.columns:
                    df = tbl
                    break
            
            if df is None or df.empty:
                logger.warning("No data table found on page %d", page)
                break
                
            # Clean column names
            # Using regex to replace any whitespace (spaces, tabs, \xa0) with underscores
            df.columns = df.columns.str.lower().str.replace(r'\s+', '_', regex=True)
            df = df.rename(columns={"δown": "delta_own"})
            
            # Ensure filing_date exists before doing cutoff logic
            if "filing_date" in df.columns:
                df["filing_date"] = pd.to_datetime(df["filing_date"], errors="coerce")
                
                # Check for cutoff
                if max_filing_date is not None:
                    # Filter out anything older than max_filing_date
                    valid_rows = df[df["filing_date"] > max_filing_date]
                    if valid_rows.empty:
                        logger.info("Reached maxFilingDate on page %d. Stopping.", page)
                        break
                    df = valid_rows
            
            # Clean numeric columns (price, qty, owned, value)
            for col in ["price", "qty", "owned", "value"]:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace("$", "").str.replace(",", "").str.replace(">", "").str.replace("<", "").replace("nan", None)
                    df[col] = pd.to_numeric(df[col], errors="coerce")
            
            # Clean delta_own
            if "delta_own" in df.columns:
                def clean_delta(val: Any) -> Optional[float]:
                    s = str(val).strip()
                    if s.lower() == "new":
                        return 1.0
                    s = s.replace("%", "").replace(">", "").replace("<", "")
                    try:
                        return float(s) / 100.0
                    except ValueError:
                        return None
                df["delta_own"] = df["delta_own"].apply(clean_delta)
            
            # Clean transaction_date
            if "trade_date" in df.columns:
                df["transaction_date"] = pd.to_datetime(df["trade_date"], errors="coerce")
                
            # Generate ID
            df["id"] = df.apply(self._generate_id, axis=1)
            
            # Yield records
            published_on_page = 0
            for _, row in df.iterrows():
                try:
                    payload: Dict[str, Any] = row.to_dict()
                    payload["currency"] = "USD"
                    payload["market"] = "US"
                    payload["extracted_at"] = extracted_at
                    
                    # Convert pandas NaT/NaN to None
                    for k, v in payload.items():
                        if pd.isna(v):
                            payload[k] = None
                            
                    tx = InsiderTransaction.model_validate(payload)
                    yield tx
                    published_on_page += 1
                except Exception as exc:
                    ticker = row.get("ticker", "Unknown")
                    logger.warning("Skipping insider transaction for %s: %s", ticker, exc)
                    
            logger.info("Yielded %d transactions from page %d", published_on_page, page)
            
            # If we didn't get a full page, it means we're at the end
            if len(tables) > 0 and len(df) < self.records_per_page and max_filing_date is None:
                # Be careful here: the count of the parsed df might be lower if there are errors,
                # but if the raw table has fewer than records_per_page, we are definitely at the end.
                raw_table_len = len(tables[-3]) if len(tables) >= 3 else len(df)
                if raw_table_len < self.records_per_page:
                     logger.info("Reached the end of available records on page %d.", page)
                     break
            
            # Delay before next page
            if page >= 99:
                logger.info("Reached maximum page limit (99). Stopping.")
                break
                
            logger.debug("Sleeping for %d seconds...", self.delay_seconds)
            time.sleep(self.delay_seconds)
            page += 1

    @staticmethod
    def _generate_id(row: pd.Series) -> str:
        ticker = str(row.get("ticker", ""))
        filing_date = str(row.get("filing_date", ""))
        insider_name = str(row.get("insider_name", ""))
        trade_type = str(row.get("trade_type", ""))
        qty = str(row.get("qty", ""))
        unique_string = f"{ticker}_{filing_date}_{insider_name}_{trade_type}_{qty}"
        return hashlib.md5(unique_string.encode("utf-8")).hexdigest()