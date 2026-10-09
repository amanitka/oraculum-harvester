"""SEC 13F bulk data provider.

Downloads the SEC quarterly bulk ZIP directly — one HTTP request yields
all ~6,000 institutional filers for the entire quarter.

Intentionally separate from SecProvider (which uses edgartools for
individual company 8-K/10-K/10-Q filings). Different access pattern,
different library, different responsibility.
"""

from __future__ import annotations

import logging
import zipfile
from datetime import date
from pathlib import Path
from typing import Iterator

import pandas as pd
import requests

from common.config import config
from common.domain.sec_13f import Sec13FFiler

logger = logging.getLogger(__name__)

# SEC changed value reporting from thousands → dollars for filings
# covering periods ending on or after June 28, 2024 (SEC Release 34-97308).
# For simplicity we use a conservative date-based cutoff.
_VALUE_IN_DOLLARS_FROM = date(2024, 6, 28)

# Bulk ZIP column names as published by the SEC
_SUBMISSION_COLS = ["ACCESSION_NUMBER", "CIK", "SUBMISSIONTYPE", "FILING_DATE", "PERIODOFREPORT"]
_COVERPAGE_COLS  = ["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]
_INFOTABLE_COLS  = [
    "ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP",
    "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL",
    "INVESTMENTDISCRETION",
    "VOTING_AUTH_SOLE", "VOTING_AUTH_SHARED", "VOTING_AUTH_NONE",
]


class Sec13FProvider:
    """Fetches SEC 13F institutional holdings via the quarterly bulk ZIP.

    Streams the download to disk and streams TSV parsing in chunks with minimal RAM overhead.
    """

    def __init__(self, chunk_size: int | None = None) -> None:
        self.chunk_size = chunk_size or config.harvester_default_chunk_size
        self._user_agent = config.sec_user_agent
        self._bulk_bases = config.sec_bulk_13f_base_urls

    @staticmethod
    def _build_candidate_filenames(year: int, quarter: int) -> list[str]:
        candidates = []
        if quarter == 1:
            candidates.append(f"01mar{year}-31may{year}_form13f.zip")
        elif quarter == 2:
            candidates.append(f"01jun{year}-31aug{year}_form13f.zip")
        elif quarter == 3:
            candidates.append(f"01sep{year}-30nov{year}_form13f.zip")
        elif quarter == 4:
            candidates.append(f"01dec{year}-28feb{year + 1}_form13f.zip")
            candidates.append(f"01dec{year}-29feb{year + 1}_form13f.zip")
        candidates.append(f"{year}q{quarter}_13f.zip")
        return candidates

    def download_to_file(self, year: int, quarter: int, dest_path: Path) -> Path | None:
        """Stream-download the quarterly 13F bulk ZIP directly to a disk file.

        Returns the destination Path on success, or None if the file is not yet available (e.g. 404).
        """
        candidates = self._build_candidate_filenames(year, quarter)
        headers = {"User-Agent": self._user_agent}

        dest_path.parent.mkdir(parents=True, exist_ok=True)
        last_resp = None

        attempted_urls: list[str] = []

        for base in self._bulk_bases:
            for filename in candidates:
                url = f"{base.rstrip('/')}/{filename}"
                attempted_urls.append(url)
                logger.info("Attempting 13F bulk ZIP download from %s", url)
                try:
                    with requests.get(url, headers=headers, timeout=300, stream=True) as resp:
                        if resp.status_code == 200:
                            total_bytes = 0
                            with open(dest_path, "wb") as f:
                                for chunk in resp.iter_content(chunk_size=1024 * 1024):
                                    if chunk:
                                        f.write(chunk)
                                        total_bytes += len(chunk)
                            logger.info("Successfully downloaded %s (%d MB) to %s", filename, total_bytes // 1_048_576, dest_path)
                            return dest_path
                        last_resp = resp
                except requests.RequestException as e:
                    logger.warning("Failed downloading %s: %s", url, e)

        if last_resp is not None and last_resp.status_code == 404:
            logger.info(
                "SEC 13F bulk dataset for %dQ%d is not yet available on SEC servers (404 Not Found at %s, checked URLs: %s).",
                year,
                quarter,
                last_resp.url,
                attempted_urls,
            )
            return None

        if last_resp is not None:
            last_resp.raise_for_status()

        logger.info(
            "Could not find SEC 13F bulk ZIP for %dQ%d across configured URLs: %s",
            year,
            quarter,
            attempted_urls,
        )
        return None

    def stream_holdings_chunks(
        self, zf: zipfile.ZipFile, period_of_report: date, filing_date: date
    ) -> Iterator[pd.DataFrame]:
        """Stream-parse INFOTABLE.tsv in chunks, merge metadata, and yield transformed DataFrames.

        Memory efficient: keeps only manager metadata (~10k rows) in RAM while streaming
        3.4M holdings in 250k-row slices without instantiating millions of Python objects.
        """
        logger.info("Loading SUBMISSION.tsv and COVERPAGE.tsv manager metadata...")
        submission, coverpage = self._load_base_frames(zf)
        logger.info("Loaded %d submissions and %d coverpages", len(submission), len(coverpage))

        # Merge submission (CIK) and coverpage (FILINGMANAGER_NAME) by accession number
        managers = submission[["ACCESSION_NUMBER", "CIK"]].merge(
            coverpage[["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]],
            on="ACCESSION_NUMBER",
            how="left",
        )
        del submission, coverpage

        # Open fresh stream to INFOTABLE.tsv inside the ZIP (supports root or subfolder)
        infotable_entry = self._find_zip_entry(zf, "INFOTABLE.tsv")
        infotable_file = zf.open(infotable_entry)
        reader = pd.read_csv(
            infotable_file,
            sep="\t",
            dtype=str,
            chunksize=self.chunk_size,
            on_bad_lines="skip",
        )

        part = 0
        try:
            for chunk_df in reader:
                part += 1
                chunk_df.columns = [c.strip().upper() for c in chunk_df.columns]
                present = [c for c in _INFOTABLE_COLS if c in chunk_df.columns]
                chunk_df = chunk_df[present]

                # Merge manager metadata
                merged = chunk_df.merge(managers, on="ACCESSION_NUMBER", how="left")
                del chunk_df

                # Normalize and format columns to match target schema
                transformed = self._format_holdings_dataframe(merged, period_of_report, filing_date)
                del merged

                logger.info("Prepared holdings chunk #%d (%d rows)", part, len(transformed))
                yield transformed
        finally:
            infotable_file.close()

    def parse_filers(
        self, zf: zipfile.ZipFile, period_of_report: date
    ) -> list[Sec13FFiler]:
        """Extract unique filers from SUBMISSION.tsv + COVERPAGE.tsv."""
        logger.info("Extracting unique filers from SUBMISSION.tsv and COVERPAGE.tsv...")
        submission, coverpage = self._load_base_frames(zf)

        merged = submission.merge(
            coverpage[["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]],
            on="ACCESSION_NUMBER",
            how="left",
        )

        filers_df = merged[merged["SUBMISSIONTYPE"].isin(["13F-HR", "13F-HR/A"])].copy()
        filers_df["CIK"] = filers_df["CIK"].astype(str).str.strip().str.zfill(10)
        filers_df["parsed_filing_date"] = pd.to_datetime(filers_df["FILING_DATE"], errors="coerce")
        # Sort by filing date ascending so drop_duplicates(keep='last') keeps the newest filing
        filers_df = filers_df.sort_values(by=["parsed_filing_date", "ACCESSION_NUMBER"]).drop_duplicates(
            subset=["CIK"], keep="last"
        )

        filers: list[Sec13FFiler] = []
        for _, row in filers_df.iterrows():
            sub_type = str(row.get("SUBMISSIONTYPE", "")).strip()
            f_date = row["parsed_filing_date"].date() if pd.notna(row["parsed_filing_date"]) else period_of_report
            filers.append(Sec13FFiler(
                cik=row["CIK"],
                manager_name=str(row.get("FILINGMANAGER_NAME", "")).strip(),
                form_type=sub_type,
                filing_date=f_date,
                accession_number=str(row["ACCESSION_NUMBER"]).strip(),
                year=period_of_report.year,
                quarter=(period_of_report.month - 1) // 3 + 1,
            ))
        logger.info("Extracted %d unique institutional filers (13F-HR / 13F-HR/A)", len(filers))
        return filers

    @staticmethod
    def _find_zip_entry(zf: zipfile.ZipFile, target_filename: str) -> str:
        """Locate a file in the ZIP archive matching target_filename regardless of folder path or case."""
        target_lower = target_filename.lower()
        for name in zf.namelist():
            if Path(name).name.lower() == target_lower:
                return name
        raise KeyError(
            f"There is no item named '{target_filename}' (even inside subdirectories) in the archive. "
            f"Available entries: {zf.namelist()}"
        )

    def _load_base_frames(
        self, zf: zipfile.ZipFile
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load and minimally clean SUBMISSION.tsv and COVERPAGE.tsv."""
        submission = self._read_tsv(zf, "SUBMISSION.tsv", _SUBMISSION_COLS)
        coverpage  = self._read_tsv(zf, "COVERPAGE.tsv",  _COVERPAGE_COLS)
        return submission, coverpage

    @classmethod
    def _read_tsv(cls, zf: zipfile.ZipFile, filename: str, cols: list[str]) -> pd.DataFrame:
        """Read a TSV from the ZIP, keeping only the columns we need."""
        entry_name = cls._find_zip_entry(zf, filename)
        with zf.open(entry_name) as f:
            df = pd.read_csv(
                f,
                sep="\t",
                dtype=str,
                on_bad_lines="skip",
            )
        df.columns = [c.strip().upper() for c in df.columns]
        present = [c for c in cols if c in df.columns]
        return df[present]

    @classmethod
    def _format_holdings_dataframe(
        cls, df: pd.DataFrame, period: date, filing_date: date
    ) -> pd.DataFrame:
        """Vectorized transformation of holding chunk to schema-matching DataFrame."""
        def _get_num(col: str) -> pd.Series:
            if col in df.columns:
                return pd.to_numeric(df[col], errors="coerce").fillna(0).astype("int64")
            return pd.Series(0, index=df.index, dtype="int64")

        def _get_str(col: str) -> pd.Series:
            if col in df.columns:
                return df[col].fillna("").astype(str).str.strip()
            return pd.Series("", index=df.index, dtype=str)

        val = _get_num("VALUE")
        if period < _VALUE_IN_DOLLARS_FROM:
            val = val * 1000

        shares = _get_num("SSHPRNAMT")
        v_sole = _get_num("VOTING_AUTH_SOLE")
        v_shared = _get_num("VOTING_AUTH_SHARED")
        v_none = _get_num("VOTING_AUTH_NONE")

        opt_type = _get_str("PUTCALL")
        opt_type = opt_type.replace({"": None, "nan": None, "None": None})

        return pd.DataFrame({
            "accession_number": _get_str("ACCESSION_NUMBER"),
            "cik": _get_str("CIK").str.zfill(10),
            "manager_name": _get_str("FILINGMANAGER_NAME"),
            "report_period": period,
            "filing_date": filing_date,
            "issuer_name": _get_str("NAMEOFISSUER"),
            "class_title": _get_str("TITLEOFCLASS"),
            "cusip": _get_str("CUSIP"),
            "value_usd": val,
            "shares_or_prn_amount": shares,
            "shares_or_prn_type": _get_str("SSHPRNAMTTYPE"),
            "option_type": opt_type,
            "investment_discretion": _get_str("INVESTMENTDISCRETION"),
            "voting_auth_sole": v_sole,
            "voting_auth_shared": v_shared,
            "voting_auth_none": v_none,
        })
