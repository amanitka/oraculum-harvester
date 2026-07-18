import logging
import hashlib
import gc
from datetime import datetime, timezone, timedelta, date
from typing import Any

from common.requests.sec_documents import FetchSecDocumentsRequest
from common.domain.data_file_ready import DataFileReadyEvent, DataFileStatus
from common.domain.ticker_document import TickerDocument
from harvester.providers.sec_provider import SecProvider
from harvester.publishers import data_file_ready
import asyncio
from harvester.services.parquet_writer import write_to_parquet

logger = logging.getLogger(__name__)

class SecDocumentService:
    HISTORY_LIMIT_YEARS: int = 2

    def __init__(self, provider: SecProvider):
        self.provider = provider

    @property
    def history_limit_date(self) -> date:
        """Get the cutoff date for historical SEC filings based on the configured limit."""
        return datetime.now(timezone.utc).date() - timedelta(days=self.HISTORY_LIMIT_YEARS * 365)

    def _generate_id(self, source: str, accession_number: str, document_subtype: str) -> str:
        """SHA256(source + accession_number + document_subtype)"""
        raw = f"{source}{accession_number}{document_subtype}".encode('utf-8')
        return hashlib.sha256(raw).hexdigest()

    def _parse_report_period(self, report_period: Any) -> date | None:
        """Safely parses various report_period formats into a native date object."""
        if not report_period:
            return None
        if isinstance(report_period, str):
            try:
                return datetime.strptime(report_period, "%Y-%m-%d").date()
            except ValueError:
                return None
        elif isinstance(report_period, datetime):
            return report_period.date()
        return report_period

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
                    if doc_type == "SEC_8K":
                        records, status = self._process_8k(ticker, market, source, hw_date, cik)
                        all_records.extend(records)
                        refresh_statuses.append(status)
                        
                    elif doc_type == "SEC_10K":
                        records, status = self._process_10k(ticker, market, source, hw_date, cik)
                        all_records.extend(records)
                        refresh_statuses.append(status)
                        
                    elif doc_type == "SEC_10Q":
                        records, status = self._process_10q(ticker, market, source, hw_date, cik)
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
            correlation_id = str(getattr(request, 'correlation_id', 'manual_run'))
            
            meta = await asyncio.to_thread(
                write_to_parquet,
                models=all_records,
                dataset="ticker_document",
                correlation_id=correlation_id,
                market="us"
            )
            
            event = DataFileReadyEvent(
                dataset="ticker_document",
                file_name=meta["path"],
                correlation_id=correlation_id,
                file_checksum=meta["checksum"],
                record_count=meta["count"],
                file_statuses=refresh_statuses
            )
            
            await data_file_ready.publish(event)
            logger.info(f"Published DataFileReadyEvent for {meta['count']} SEC documents")
        else:
            # Even if no files were found, we must still publish an event to update the sync status in DB
            logger.info("No new SEC documents found, publishing empty event with sync status")
            event = DataFileReadyEvent(
                dataset="ticker_document",
                file_name="",
                correlation_id=str(getattr(request, 'correlation_id', 'manual_run')),
                file_checksum="",
                record_count=0,
                file_statuses=refresh_statuses
            )
            await data_file_ready.publish(event)

        # Run garbage collection and trim malloc to release memory back to the OS
        from common.memory import release_memory
        release_memory()

    def _process_8k(self, ticker: str, market: str, source: str, hw_date: date | None, cik: str | None = None) -> tuple[list[TickerDocument], DataFileStatus]:
        """Fetches 8-Ks and extracts EX99_1."""
        limit_date = self.history_limit_date
        fetch_after = hw_date if hw_date else limit_date
        filings = self.provider.fetch_8k(ticker, after_date=fetch_after, cik=cik)
        
        if not filings:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="SEC_8K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="No new filing found"
            )
            
        records = []
        latest_date = None
        
        for f in filings:
            if not f.get("text"):
                continue
                
            report_period = f.get("report_period")
            rp_date = self._parse_report_period(report_period)
                    
            if rp_date and rp_date < limit_date:
                logger.warning(f"Skipping 8-K filing for {ticker} because report_period {report_period} is older than {self.HISTORY_LIMIT_YEARS} years ({limit_date})")
                continue
                
            doc_subtype = "SEC_EX99_1"
            doc_id = self._generate_id(source, f["accession_number"], doc_subtype)
            
            records.append(TickerDocument(
                id=doc_id,
                ticker=ticker,
                market=market,
                source=source,
                document_type="SEC_8K",
                document_subtype=doc_subtype,
                accession_number=f["accession_number"],
                source_url=f["source_url"],
                report_period=f["report_period"],
                filing_date=f["filing_date"],
                content=f["text"],
                extracted_at=datetime.now(timezone.utc)
            ))
            
            if not latest_date or f["filing_date"] > latest_date:
                latest_date = f["filing_date"]
                
        if not records:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="SEC_8K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="No EX99_1 found in recent filings"
            )
            
        return records, DataFileStatus(
            ticker=ticker, market=market, source=source, file_type="SEC_8K",
            latest_processed_date=str(latest_date) if latest_date else None, status="COMPLETED", extraction_status="FULL", message=None
        )

    def _process_10k(self, ticker: str, market: str, source: str, hw_date: date | None, cik: str | None = None) -> tuple[list[TickerDocument], DataFileStatus]:
        """Fetches 10-Ks and extracts Risk Factors and Management Discussion."""
        limit_date = self.history_limit_date
        fetch_after = hw_date if hw_date else limit_date
        filings = self.provider.fetch_10k(ticker, after_date=fetch_after, cik=cik)
        
        if not filings:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="SEC_10K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="No new filing found"
            )
            
        records = []
        latest_date = None
        
        for f in filings:
            report_period = f.get("report_period")
            rp_date = self._parse_report_period(report_period)
                    
            if rp_date and rp_date < limit_date:
                logger.warning(f"Skipping 10-K filing for {ticker} because report_period {report_period} is older than {self.HISTORY_LIMIT_YEARS} years ({limit_date})")
                continue
                
            risk_factors = f.get("risk_factors")
            management_discussion = f.get("management_discussion")
            
            if risk_factors:
                doc_id = self._generate_id(source, f["accession_number"], "SEC_RF")
                records.append(TickerDocument(
                    id=doc_id, ticker=ticker, market=market, source=source,
                    document_type="SEC_10K", document_subtype="SEC_RF",
                    accession_number=f["accession_number"], source_url=f["source_url"],
                    report_period=f["report_period"],
                    filing_date=f["filing_date"], content=risk_factors,
                    extracted_at=datetime.now(timezone.utc)
                ))
                
            if management_discussion:
                doc_id = self._generate_id(source, f["accession_number"], "SEC_MD")
                records.append(TickerDocument(
                    id=doc_id, ticker=ticker, market=market, source=source,
                    document_type="SEC_10K", document_subtype="SEC_MD",
                    accession_number=f["accession_number"], source_url=f["source_url"],
                    report_period=f["report_period"],
                    filing_date=f["filing_date"], content=management_discussion,
                    extracted_at=datetime.now(timezone.utc)
                ))
                
            if not latest_date or f["filing_date"] > latest_date:
                latest_date = f["filing_date"]
                
        if not records:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="SEC_10K",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="Missing both RF and MD in all recent filings"
            )
            
        return records, DataFileStatus(
            ticker=ticker, market=market, source=source, file_type="SEC_10K",
            latest_processed_date=str(latest_date) if latest_date else None, status="COMPLETED", extraction_status="FULL", message=None
        )

    def _process_10q(self, ticker: str, market: str, source: str, hw_date: date | None, cik: str | None = None) -> tuple[list[TickerDocument], DataFileStatus]:
        """Fetches 10-Qs and extracts Risk Factors and Management Discussion."""
        limit_date = self.history_limit_date
        fetch_after = hw_date if hw_date else limit_date
        filings = self.provider.fetch_10q(ticker, after_date=fetch_after, cik=cik)
        
        if not filings:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="SEC_10Q",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="No new filing found"
            )
            
        records = []
        latest_date = None
        
        for f in filings:
            report_period = f.get("report_period")
            rp_date = self._parse_report_period(report_period)
                    
            if rp_date and rp_date < limit_date:
                logger.warning(f"Skipping 10-Q filing for {ticker} because report_period {report_period} is older than {self.HISTORY_LIMIT_YEARS} years ({limit_date})")
                continue
                
            risk_factors = f.get("risk_factors")
            management_discussion = f.get("management_discussion")
            
            if risk_factors:
                doc_id = self._generate_id(source, f["accession_number"], "SEC_RF")
                records.append(TickerDocument(
                    id=doc_id, ticker=ticker, market=market, source=source,
                    document_type="SEC_10Q", document_subtype="SEC_RF",
                    accession_number=f["accession_number"], source_url=f["source_url"],
                    report_period=f["report_period"],
                    filing_date=f["filing_date"], content=risk_factors,
                    extracted_at=datetime.now(timezone.utc)
                ))
                
            if management_discussion:
                doc_id = self._generate_id(source, f["accession_number"], "SEC_MD")
                records.append(TickerDocument(
                    id=doc_id, ticker=ticker, market=market, source=source,
                    document_type="SEC_10Q", document_subtype="SEC_MD",
                    accession_number=f["accession_number"], source_url=f["source_url"],
                    report_period=f["report_period"],
                    filing_date=f["filing_date"], content=management_discussion,
                    extracted_at=datetime.now(timezone.utc)
                ))
                
            if not latest_date or f["filing_date"] > latest_date:
                latest_date = f["filing_date"]
                
        if not records:
            return [], DataFileStatus(
                ticker=ticker, market=market, source=source, file_type="SEC_10Q",
                latest_processed_date=None, status="COMPLETED", extraction_status="EMPTY", message="Missing both RF and MD in all recent filings"
            )
            
        return records, DataFileStatus(
            ticker=ticker, market=market, source=source, file_type="SEC_10Q",
            latest_processed_date=str(latest_date) if latest_date else None, status="COMPLETED", extraction_status="FULL", message=None
        )
