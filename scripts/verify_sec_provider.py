import os
import sys
import logging
from pathlib import Path
from datetime import datetime, timedelta

# Add project root to sys.path so we can import harvester
project_root = Path(__file__).resolve().parent.parent
sys.path.append(str(project_root))

from harvester.providers.sec_provider import SecProvider

logger = logging.getLogger(__name__)

def setup_logging():
    """Configure detailed logging for manual verification."""
    # Set root logger to INFO so we don't get too much noise from other libs
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    
    # Specifically set sec_provider to DEBUG
    sec_logger = logging.getLogger("harvester.providers.sec_provider")
    sec_logger.setLevel(logging.DEBUG)

def save_text(ticker: str, filing_type: str, date: str, section: str, text: str):
    """Saves the extracted text to a local file for verification."""
    if not text:
        return
        
    output_dir = project_root / "verification_output" / ticker
    output_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{date}_{filing_type}_{section}.txt"
    filepath = output_dir / filename
    
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(text)
    logger.info(f"Saved {section} to {filepath}")

def verify_ticker(ticker: str, years_back: int = 5):
    logger.info(f"Starting verification for {ticker} (Last {years_back} years)")
    logger.info("-" * 50)
    
    provider = SecProvider()
    after_date = (datetime.now() - timedelta(days=years_back * 365)).date()
    
    logger.info("--- Fetching 8-K Exhibit 99.1 ---")
    eight_k_results = provider.fetch_8k(ticker, after_date=after_date)
    for result in eight_k_results:
        save_text(ticker, "8-K", str(result["filing_date"]), "exhibit_99.1", result.get("text", ""))

    logger.info("--- Fetching 10-K Risk Factors and Management Discussion ---")
    ten_k_results = provider.fetch_10k(ticker, after_date=after_date)
    for result in ten_k_results:
        save_text(ticker, "10-K", str(result["filing_date"]), "risk_factors", result.get("risk_factors", ""))
        save_text(ticker, "10-K", str(result["filing_date"]), "management_discussion", result.get("management_discussion", ""))

    logger.info("-" * 50)
    logger.info(f"Verification complete for {ticker}. Check 'verification_output/{ticker}' for extracted text files.")

if __name__ == "__main__":
    setup_logging()
    
    ticker_to_check = sys.argv[1] if len(sys.argv) > 1 else "AAPL"
    years = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    
    verify_ticker(ticker_to_check, years)
