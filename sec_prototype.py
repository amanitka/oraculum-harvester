import sys
from pathlib import Path
from edgar import set_identity, Company
from lxml import html

class SecEdgarClient:
    """Handles communication with the SEC EDGAR database."""
    def __init__(self, user_agent: str = "Oraculum_Harvester user@oraculum.local"):
        set_identity(user_agent)

    def fetch_recent_8k_filings(self, ticker: str, limit: int = 10):
        company = Company(ticker)
        if not company:
            raise ValueError(f"Company {ticker} not found.")
        return company.get_filings(form="8-K").latest(limit)

class ExhibitParser:
    """Parses and extracts clean text from SEC Exhibit attachments."""
    
    @staticmethod
    def is_exhibit_99(attachment) -> bool:
        doc_type = attachment.document_type.lower() if attachment.document_type else ""
        desc = attachment.description.lower() if attachment.description else ""
        return "ex-99" in doc_type or "99" in doc_type or "exhibit 99" in desc

    @staticmethod
    def extract_clean_text(raw_content: bytes | str) -> str:
        if not raw_content:
            return ""
        try:
            # Parse HTML and extract raw text using lxml
            document = html.fromstring(raw_content)
            raw_text = document.text_content()
            
            # Clean up excessive whitespace and empty lines
            lines = (line.strip() for line in raw_text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            return '\n'.join(chunk for chunk in chunks if chunk)
        except Exception as e:
            print(f"Error parsing HTML: {e}")
            return str(raw_content)

class PrototypeRunner:
    """Coordinates the fetching, parsing, and saving of transcripts."""
    
    def __init__(self, output_dir: str = "temp_transcripts"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = SecEdgarClient()

    def run(self, ticker: str):
        print(f"Fetching 8-K filings for {ticker}...")
        try:
            filings = self.client.fetch_recent_8k_filings(ticker)
            self._process_filings(ticker, filings)
        except Exception as e:
            print(f"Failed to fetch filings: {e}")

    def _process_filings(self, ticker: str, filings):
        for filing in filings:
            print(f"\n--- Checking 8-K Filed on {filing.filing_date} ---")
            self._process_attachments(ticker, filing)

    def _process_attachments(self, ticker: str, filing):
        try:
            for attachment in filing.attachments:
                if ExhibitParser.is_exhibit_99(attachment):
                    self._download_and_save(ticker, filing.filing_date, attachment)
        except Exception as e:
            print(f"Error reading attachments: {e}")

    def _download_and_save(self, ticker: str, date: str, attachment):
        print(f" -> Found {attachment.document_type} ({attachment.description}). Downloading...")
        raw_content = attachment.download()
        
        clean_text = ExhibitParser.extract_clean_text(raw_content)
        
        # Save to the temporary directory
        filename = f"{ticker}_8K_{date}_{attachment.document_type}.txt".replace(" ", "_")
        file_path = self.output_dir / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(clean_text)
            
        print(f" -> Saved clean text to {file_path}")

if __name__ == "__main__":
    ticker_arg = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    runner = PrototypeRunner()
    runner.run(ticker_arg)
