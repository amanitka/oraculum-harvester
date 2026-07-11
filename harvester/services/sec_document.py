import logging
import os
import hashlib
from datetime import datetime, timezone, timedelta, date
import pandas as pd

from common.requests.sec_documents import FetchSecDocumentsRequest, TickerDocumentItem
from common.domain.data_file_ready import DataFileReadyEvent, DataFileStatus
from harvester.providers.sec_provider import SecProvider
from harvester.publishers import data_file_ready

logger = logging.getLogger(__name__)

class SecDocumentService:
    def __init__(self, provider: SecProvider):
        self.provider = provider

    def _generate_id(self, source: str, accession_number: str, document_subtype: str) -> str:
        """SHA256(source + accession_number + document_subtype)"""
        raw = f"{source}{accession_number}{document_subtype}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    async def fetch_sec_documents(self, request: FetchSecDocumentsRequest) -> None:
        """Handles the fetch_sec_documents command."""
        logger.info(f"Processing SEC documents request for {len(request.items)} items")
        
        all_records = []
        refresh_statuses = []
        source = "SEC_EDGAR"
        
        for item in request.items:
            ticker = item.ticker
            cik = getattr(item, "cik", None)
            market = item.market
            
            for doc_req in item.document_types:
                doc_type = doc_req.document_type
                hw_date = doc_req.last_processed_file_date
                
                try:
                    if doc_type == "8K":
                        records, status = self._process_8k(ticker, market, source, hw_date, cik)
                        all_records.extend(records)
                        refresh_statuses.append(status)
                        
                    elif doc_type == "10K":
                        records, status = self._process_10k(ticker, market, source, hw_date, cik)
                        all_records.extend(records)
                        refresh_statuses.append(status)
                        
                    else:
                        logger.warning(f"Unsupported document type: {doc_type}")
                        
                except Exception as e:
                    logger.exception(f"Error processing {doc_type} for {ticker}: {e}")
                    refresh_statuses.append(DataFileStatus(
                        ticker=ticker, market=market, source=source, file_type=doc_type,
                        status="FAILED", message=str(e)
                    ))
                    
        # If we have extracted data, write to Parquet and publish event
        if all_records:
            df = pd.DataFrame(all_records)
            
            # Ensure output directory exists
            output_dir = os.environ.get("DATA_DIR", "/tmp/oraculum_data")
            os.makedirs(output_dir, exist_ok=True)
            
            run_id = getattr(request, 'run_id', None) or str(getattr(request, 'correlation_id', 'manual_run'))
            file_name = f"ticker_document_{run_id}_{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}.parquet"
            file_path = os.path.join(output_dir, file_name)
            
            df.to_parquet(file_path, engine='pyarrow')
            
            checksum = hashlib.md5(open(file_path, 'rb').read()).hexdigest()
            
            event = DataFileReadyEvent(
                dataset="ticker_document",
                path=file_name,
                run_id=run_id,
                file_checksum=checksum,
                record_count=len(df),
                file_statuses=refresh_statuses
            )
            
            await data_file_ready.publish(event)
            logger.info(f"Published DataFileReadyEvent for {len(df)} SEC documents")
        else:
            # Even if no files were found, we must still publish an event to update the sync status in DB
            logger.info("No new SEC documents found, publishing empty event with sync status")
            event = DataFileReadyEvent(
                dataset="ticker_document",
                path="",
                run_id=getattr(request, 'run_id', None) or str(getattr(request, 'correlation_id', 'manual_run')),
                file_checksum="",
                record_count=0,
                file_statuses=refresh_statuses
            )
            await data_file_ready.publish(event)

    def _process_8k(self, ticker: str, market: str, source: str, hw_date: date | None, cik: str | None = None) -> tuple[list[dict], DataFileStatus]:
        """Fetches 8-Ks and extracts EX99_1."""
        fetch_after = hw_date if hw_date else (datetime.now(timezone.utc).date() - timedelta(days=5 * 365))
        filings = self.provider.fetch_8k(ticker, after_date=fetch_after, cik=cik)
        
        if not filings:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="8K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="No new filing found"
            )
            
        records = []
        latest_date = None
        
        for f in filings:
            if not f.get("text"):
                continue
                
            doc_subtype = "EX99_1"
            doc_id = self._generate_id(source, f["accession_number"], doc_subtype)
            
            records.append({
                "id": doc_id,
                "ticker": ticker,
                "market": market,
                "source": source,
                "document_type": "8K",
                "document_subtype": doc_subtype,
                "accession_number": f["accession_number"],
                "source_url": f["source_url"],
                "report_period": f["report_period"],
                "filing_date": f["filing_date"],
                "content": f["text"],
                "extracted_at": datetime.now(timezone.utc).isoformat()
            })
            
            if not latest_date or f["filing_date"] > latest_date:
                latest_date = f["filing_date"]
                
        if not records:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="8K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="No EX99_1 found in recent filings"
            )
            
        return records, DataFileStatus(
            ticker=ticker, market=market, source=source, file_type="8K",
            latest_processed_date=str(latest_date) if latest_date else None, status="COMPLETED", extraction_status="FULL", message=None
        )

    def _process_10k(self, ticker: str, market: str, source: str, hw_date: date | None, cik: str | None = None) -> tuple[list[dict], DataFileStatus]:
        """Fetches 10-Ks and extracts Risk Factors and Management Discussion."""
        fetch_after = hw_date if hw_date else (datetime.now(timezone.utc).date() - timedelta(days=5 * 365))
        filings = self.provider.fetch_10k(ticker, after_date=fetch_after, cik=cik)
        
        if not filings:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="10K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="No new filing found"
            )
            
        records = []
        latest_date = None
        
        for f in filings:
            risk_factors = f.get("risk_factors")
            management_discussion = f.get("management_discussion")
            
            if risk_factors:
                doc_id = self._generate_id(source, f["accession_number"], "RF")
                records.append({
                    "id": doc_id, "ticker": ticker, "market": market, "source": source,
                    "document_type": "10K", "document_subtype": "RF",
                    "accession_number": f["accession_number"], "source_url": f["source_url"],
                    "report_period": f["report_period"],
                    "filing_date": f["filing_date"], "content": risk_factors,
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })
                
            if management_discussion:
                doc_id = self._generate_id(source, f["accession_number"], "MD")
                records.append({
                    "id": doc_id, "ticker": ticker, "market": market, "source": source,
                    "document_type": "10K", "document_subtype": "MD",
                    "accession_number": f["accession_number"], "source_url": f["source_url"],
                    "report_period": f["report_period"],
                    "filing_date": f["filing_date"], "content": management_discussion,
                    "extracted_at": datetime.now(timezone.utc).isoformat()
                })
                
            if not latest_date or f["filing_date"] > latest_date:
                latest_date = f["filing_date"]
                
        if not records:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="10K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="Missing both RF and MD in all recent filings"
            )
            
        return records, DataFileStatus(
            ticker=ticker, market=market, source=source, file_type="10K",
            latest_processed_date=str(latest_date) if latest_date else None, status="COMPLETED", extraction_status="FULL", message=None
        )
