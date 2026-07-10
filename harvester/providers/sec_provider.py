import logging
from edgar import set_identity, Company
from lxml import html

logger = logging.getLogger(__name__)

class SecProvider:
    """Provider for fetching SEC EDGAR filings."""
    
    def __init__(self, user_agent: str = "Oraculum_Harvester user@oraculum.local"):
        # EDGAR requires a user agent
        set_identity(user_agent)

    def _get_url(self, filing) -> str:
        """Safely extract URL from filing."""
        if hasattr(filing, "homepage_url"): return filing.homepage_url
        if hasattr(filing, "document_url"): return filing.document_url
        if hasattr(filing, "url"): return filing.url
        return ""

    def fetch_exhibit_99_1(self, ticker: str, limit: int = 5) -> list[dict]:
        """Fetches the latest EX-99.1 filings and extracts clean text."""
        company = Company(ticker)
        if not company:
            logger.error(f"Company {ticker} not found on EDGAR.")
            return []
        
        results = []
        try:
            # Fetch recent 8-K filings
            filings = company.get_filings(form="8-K").latest(limit)
            if not isinstance(filings, list): # handle edgar filing list wrapper
                filings = [filings] if filings else []
                
            for filing in filings:
                for attachment in filing.attachments:
                    doc_type = attachment.document_type.lower() if attachment.document_type else ""
                    desc = attachment.description.lower() if attachment.description else ""
                    
                    if "ex-99" in doc_type or "99" in doc_type or "exhibit 99" in desc:
                        raw_content = attachment.download()
                        clean_text = self._extract_clean_text(raw_content)
                        if clean_text:
                            results.append({
                                "accession_number": filing.accession_no,
                                "source_url": self._get_url(filing),
                                "report_period": getattr(filing, "report_date", filing.filing_date) or filing.filing_date,
                                "filing_date": filing.filing_date,
                                "text": clean_text
                            })
                        break # Only need the primary exhibit 99 from this filing
        except Exception as e:
            logger.error(f"Error fetching filings for {ticker}: {e}")
            
        return results

    def fetch_10k_items(self, ticker: str, limit: int = 2) -> list[dict]:
        """Fetches 10-K filings and attempts to extract Item 1A and Item 7."""
        company = Company(ticker)
        if not company:
            logger.error(f"Company {ticker} not found on EDGAR.")
            return []
        
        results = []
        try:
            # Fetch recent 10-K filings
            filings = company.get_filings(form="10-K").latest(limit)
            if not isinstance(filings, list):
                filings = [filings] if filings else []
                
            for filing in filings:
                # `edgartools` provides a .tenk object for 10-K filings
                tenk = filing.obj() if hasattr(filing, "obj") else None
                item_1a_text = None
                item_7_text = None
                
                if tenk:
                    # Depending on edgartools version, tenk might have item_1a and item_7
                    if hasattr(tenk, "item_1a"): item_1a_text = tenk.item_1a
                    if hasattr(tenk, "item_7"): item_7_text = tenk.item_7
                
                # We return the dictionary even if items are missing, so the service can log partial/empty
                results.append({
                    "accession_number": filing.accession_no,
                    "source_url": self._get_url(filing),
                    "report_period": getattr(filing, "report_date", filing.filing_date) or filing.filing_date,
                    "filing_date": filing.filing_date,
                    "item_1a": self._extract_clean_text(item_1a_text) if item_1a_text else None,
                    "item_7": self._extract_clean_text(item_7_text) if item_7_text else None
                })
        except Exception as e:
            logger.error(f"Error fetching 10-K for {ticker}: {e}")
            
        return results

    def _extract_clean_text(self, raw_content: bytes | str) -> str:
        """Strips HTML and cleans whitespace."""
        if not raw_content:
            return ""
        try:
            document = html.fromstring(raw_content)
            raw_text = document.text_content()
            
            # Clean up excessive whitespace
            lines = (line.strip() for line in raw_text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return '\n'.join(chunk for chunk in chunks if chunk)
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return str(raw_content)
