import logging
from edgar import set_identity, Company
from lxml import html
from datetime import date, datetime

logger = logging.getLogger(__name__)

class SecProvider:
    """Provider for fetching SEC EDGAR filings."""
    
    def __init__(self, user_agent: str = "Oraculum_Harvester user@oraculum.local"):
        # EDGAR requires a user agent
        set_identity(user_agent)

    @staticmethod
    def _get_url(filing) -> str:
        """Safely extract URL from filing."""
        if hasattr(filing, "homepage_url"): return filing.homepage_url
        if hasattr(filing, "document_url"): return filing.document_url
        if hasattr(filing, "url"): return filing.url
        return ""

    def _get_company(self, ticker: str, cik: str | None) -> Company | None:
        """Attempts to instantiate a Company by CIK first, falling back to Ticker, catching exceptions."""
        try:
            if cik:
                try:
                    return Company(cik)
                except Exception as e:
                    logger.warning(f"[{ticker}] Company not found by CIK {cik}: {e}. Falling back to ticker.")
            return Company(ticker)
        except Exception as e:
            logger.warning(f"Company {ticker} (CIK: {cik}) not found on EDGAR: {e}")
            return None

    def fetch_8k(self, ticker: str, after_date: date | None = None, cik: str | None = None) -> list[dict]:
        """Fetches 8-K filings filed after after_date and extracts EX99_1."""
        company = self._get_company(ticker, cik)
        if not company:
            return []
        
        results = []
        try:
            logger.info(f"[{ticker}] Fetching 8-K filings since {after_date}")
            
            filings_obj = company.get_filings(form="8-K")
            
            if hasattr(filings_obj, "__iter__"):
                filings = list(filings_obj)
            elif filings_obj:
                filings = [filings_obj]
            else:
                filings = []
                
            for filing in filings:
                filing_date_obj = datetime.strptime(str(filing.filing_date)[:10], "%Y-%m-%d").date()
                if after_date and filing_date_obj <= after_date:
                    continue
                    
                url = self._get_url(filing)
                logger.debug(f"[{ticker}] Checking 8-K filing at {url} (Date: {filing.filing_date})")
                
                exhibit_found = False
                for attachment in filing.attachments:
                    doc_type = attachment.document_type.lower() if attachment.document_type else ""
                    desc = attachment.description.lower() if attachment.description else ""
                    
                    if "ex-99" in doc_type or "99" in doc_type or "exhibit 99" in desc:
                        logger.info(f"[{ticker}] Found Exhibit 99.1 in 8-K at {url}")
                        exhibit_found = True
                        raw_content = attachment.download()
                        clean_text = self.extract_clean_text(raw_content)
                        if clean_text:
                            logger.debug(f"[{ticker}] Successfully extracted clean text from Exhibit 99.1 at {url}")
                            results.append({
                                "accession_number": filing.accession_no,
                                "source_url": url,
                                "report_period": getattr(filing, "report_date", filing.filing_date) or filing.filing_date,
                                "filing_date": filing.filing_date,
                                "text": clean_text
                            })
                        else:
                            logger.warning(f"[{ticker}] Exhibit 99.1 was empty or parsing failed at {url}")
                        break # Only need the primary exhibit 99 from this filing
                        
                if not exhibit_found:
                    logger.debug(f"[{ticker}] No Exhibit 99.1 found in 8-K at {url}")
                    
        except Exception as e:
            logger.error(f"Error fetching 8-K filings for {ticker}: {e}")
            
        return results

    def fetch_10k(self, ticker: str, after_date: date | None = None, cik: str | None = None) -> list[dict]:
        """Fetches 10-K filings filed after after_date and attempts to extract Risk Factors and Management Discussion."""
        company = self._get_company(ticker, cik)
        if not company:
            return []
        
        results = []
        try:
            logger.info(f"[{ticker}] Fetching 10-K filings since {after_date}")
            
            filings_obj = company.get_filings(form="10-K")
            
            if hasattr(filings_obj, "__iter__"):
                filings = list(filings_obj)
            elif filings_obj:
                filings = [filings_obj]
            else:
                filings = []
                
            for filing in filings:
                filing_date_obj = datetime.strptime(str(filing.filing_date)[:10], "%Y-%m-%d").date()
                if after_date and filing_date_obj <= after_date:
                    continue
                    
                url = self._get_url(filing)
                logger.debug(f"[{ticker}] Checking 10-K filing at {url} (Date: {filing.filing_date})")
                
                # `edgartools` provides a .obj() object for 10-K filings
                tenk = filing.obj() if hasattr(filing, "obj") else None
                item_1a_text = None
                item_7_text = None
                
                if tenk:
                    # Depending on edgartools version, tenk might have item_1a/item_7 or risk_factors/management_discussion
                    item_1a_val = getattr(tenk, "item_1a", None) or getattr(tenk, "risk_factors", None)
                    if item_1a_val: 
                        item_1a_text = item_1a_val
                        logger.info(f"[{ticker}] Found Item 1A in 10-K at {url}")
                    
                    item_7_val = getattr(tenk, "item_7", None) or getattr(tenk, "management_discussion", None)
                    if item_7_val: 
                        item_7_text = item_7_val
                        logger.info(f"[{ticker}] Found Item 7 in 10-K at {url}")
                
                # We return the dictionary even if items are missing, so the service can log partial/empty
                results.append({
                    "accession_number": filing.accession_no,
                    "source_url": url,
                    "report_period": getattr(filing, "report_date", filing.filing_date) or filing.filing_date,
                    "filing_date": filing.filing_date,
                    "risk_factors": self.extract_clean_text(item_1a_text) if item_1a_text else None,
                    "management_discussion": self.extract_clean_text(item_7_text) if item_7_text else None
                })
        except Exception as e:
            logger.error(f"Error fetching 10-K for {ticker}: {e}")
            
        return results

    def fetch_10q(self, ticker: str, after_date: date | None = None, cik: str | None = None) -> list[dict]:
        """Fetches 10-Q filings filed after after_date and attempts to extract Risk Factors and Management Discussion."""
        company = self._get_company(ticker, cik)
        if not company:
            return []
        
        results = []
        try:
            logger.info(f"[{ticker}] Fetching 10-Q filings since {after_date}")
            
            filings_obj = company.get_filings(form="10-Q")
            
            if hasattr(filings_obj, "__iter__"):
                filings = list(filings_obj)
            elif filings_obj:
                filings = [filings_obj]
            else:
                filings = []
                
            for filing in filings:
                filing_date_obj = datetime.strptime(str(filing.filing_date)[:10], "%Y-%m-%d").date()
                if after_date and filing_date_obj <= after_date:
                    continue
                    
                url = self._get_url(filing)
                logger.debug(f"[{ticker}] Checking 10-Q filing at {url} (Date: {filing.filing_date})")
                
                tenq = filing.obj() if hasattr(filing, "obj") else None
                item_1a_text = None
                item_2_text = None
                
                if tenq:
                    item_1a_text = tenq['Item 1A']
                    item_2_text = tenq['Item 2']
                
                results.append({
                    "accession_number": filing.accession_no,
                    "source_url": url,
                    "report_period": getattr(filing, "report_date", filing.filing_date) or filing.filing_date,
                    "filing_date": filing.filing_date,
                    "risk_factors": self.extract_clean_text(item_1a_text) if item_1a_text else None,
                    "management_discussion": self.extract_clean_text(item_2_text) if item_2_text else None
                })
        except Exception as e:
            logger.error(f"Error fetching 10-Q for {ticker}: {e}")
            
        return results

    @staticmethod
    def extract_clean_text(raw_content: bytes | str) -> str:
        """Strips HTML and cleans whitespace."""
        if not raw_content:
            return ""
        try:
            if isinstance(raw_content, str):
                # lxml fails if a string has an XML encoding declaration, so we safely encode it to bytes first
                raw_content = raw_content.encode('utf-8')
                
            document = html.fromstring(raw_content)
            raw_text = document.text_content()
            
            # Clean up excessive whitespace
            lines = (line.strip() for line in raw_text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return '\n'.join(chunk for chunk in chunks if chunk)
        except Exception as e:
            logger.error(f"Error parsing HTML: {e}")
            return str(raw_content)
