"""SEC 13F bulk data provider.

Downloads the SEC quarterly bulk ZIP directly — one HTTP request yields
all ~6,000 institutional filers for the entire quarter.

Intentionally separate from SecProvider (which uses edgartools for
individual company 8-K/10-K/10-Q filings). Different access pattern,
different library, different responsibility.
"""

from __future__ import annotations

import io
import logging
import zipfile
from datetime import date
from typing import Iterator

import pandas as pd
import requests

from common.config import config
from common.domain.sec_13f import Sec13FFiler, Sec13FHolding

logger = logging.getLogger(__name__)

# SEC changed value reporting from thousands → dollars for filings
# covering periods ending on or after June 28, 2024 (SEC Release 34-97308).
# For simplicity we use a conservative date-based cutoff.
_VALUE_IN_DOLLARS_FROM = date(2024, 6, 28)

# Bulk ZIP column names as published by the SEC
_SUBMISSION_COLS = ["ACCESSION_NUMBER", "CIK", "COMPANYNAME", "PERIOD_OF_REPORT", "FILED_DATE", "FORM_TYPE"]
_COVERPAGE_COLS  = ["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]
_INFOTABLE_COLS  = [
    "ACCESSION_NUMBER", "NAMEOFISSUER", "TITLEOFCLASS", "CUSIP",
    "VALUE", "SSHPRNAMT", "SSHPRNAMTTYPE", "PUTCALL",
    "INVESTMENTDISCRETION",
    "VOTINGAUTHORITY_SOLE", "VOTINGAUTHORITY_SHARED", "VOTINGAUTHORITY_NONE",
]


class Sec13FProvider:
    """Fetches SEC 13F institutional holdings via the quarterly bulk ZIP.

    One HTTP request per quarter covers all ~6,000 institutional filers.
    Uses raw ``requests`` + ``zipfile`` + ``pandas`` — no edgartools.
    """

    CHUNK_SIZE = 250_000  # rows per Parquet file

    def __init__(self) -> None:
        self._user_agent = config.sec_user_agent
        self._bulk_base  = config.sec_bulk_13f_base_url

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_bulk_zip(self, year: int, quarter: int) -> zipfile.ZipFile:
        """Download the quarterly 13F bulk ZIP and return an in-memory ZipFile."""
        url = f"{self._bulk_base}/{year}q{quarter}_13f.zip"
        logger.info("Downloading 13F bulk ZIP for %dQ%d from %s", year, quarter, url)
        resp = requests.get(
            url,
            headers={"User-Agent": self._user_agent},
            timeout=300,
            stream=False,
        )
        resp.raise_for_status()
        logger.info("Downloaded %d MB", len(resp.content) // 1_048_576)
        return zipfile.ZipFile(io.BytesIO(resp.content))

    def parse_holdings(
        self, zf: zipfile.ZipFile, period_of_report: date, filing_date: date
    ) -> Iterator[list[Sec13FHolding]]:
        """Parse INFOTABLE.tsv joined with SUBMISSION.tsv and yield chunked lists."""
        submission, _ = self._load_base_frames(zf)
        infotable     = self._load_infotable(zf)

        merged = infotable.merge(
            submission[["ACCESSION_NUMBER", "CIK", "COMPANYNAME"]],
            on="ACCESSION_NUMBER",
            how="left",
        )

        merged = self._normalize_values(merged, period_of_report)
        merged = merged.fillna({"PUTCALL": "", "VOTINGAUTHORITY_SOLE": 0,
                                "VOTINGAUTHORITY_SHARED": 0, "VOTINGAUTHORITY_NONE": 0})

        for chunk_df in self._iter_chunks(merged):
            yield self._map_holdings(chunk_df, period_of_report, filing_date)

    def parse_filers(
        self, zf: zipfile.ZipFile, period_of_report: date
    ) -> list[Sec13FFiler]:
        """Extract unique filers from SUBMISSION.tsv + COVERPAGE.tsv."""
        submission, coverpage = self._load_base_frames(zf)

        merged = submission.merge(
            coverpage[["ACCESSION_NUMBER", "FILINGMANAGER_NAME"]],
            on="ACCESSION_NUMBER",
            how="left",
        )

        return [
            Sec13FFiler(
                cik=str(row["CIK"]).strip().zfill(10),
                manager_name=str(row.get("FILINGMANAGER_NAME") or row["COMPANYNAME"]).strip(),
                form_type=str(row["FORM_TYPE"]).strip(),
                filing_date=pd.to_datetime(row["FILED_DATE"]).date(),
                accession_number=str(row["ACCESSION_NUMBER"]).strip(),
                year=period_of_report.year,
                quarter=(period_of_report.month - 1) // 3 + 1,
            )
            for _, row in merged.iterrows()
            if str(row.get("FORM_TYPE", "")).strip() in ("13F-HR", "13F-HR/A")
        ]

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _load_base_frames(
        self, zf: zipfile.ZipFile
    ) -> tuple[pd.DataFrame, pd.DataFrame]:
        """Load and minimally clean SUBMISSION.tsv and COVERPAGE.tsv."""
        submission = self._read_tsv(zf, "SUBMISSION.tsv", _SUBMISSION_COLS)
        coverpage  = self._read_tsv(zf, "COVERPAGE.tsv",  _COVERPAGE_COLS)
        return submission, coverpage

    def _load_infotable(self, zf: zipfile.ZipFile) -> pd.DataFrame:
        return self._read_tsv(zf, "INFOTABLE.tsv", _INFOTABLE_COLS)

    @staticmethod
    def _read_tsv(zf: zipfile.ZipFile, filename: str, cols: list[str]) -> pd.DataFrame:
        """Read a TSV from the ZIP, keeping only the columns we need.

        Each zipfile.open() call returns a fresh stream from the start of the
        entry, so pd.read_csv receives the full file including the header row.
        """
        df = pd.read_csv(
            zf.open(filename),
            sep="\t",
            dtype=str,
            on_bad_lines="skip",
        )
        # Normalise column names to uppercase (SEC occasionally ships mixed case)
        df.columns = [c.strip().upper() for c in df.columns]
        present = [c for c in cols if c in df.columns]
        missing = set(cols) - set(present)
        if missing:
            logger.warning("Missing expected columns in %s: %s", filename, missing)
        return df[present]

    @staticmethod
    def _normalize_values(df: pd.DataFrame, period: date) -> pd.DataFrame:
        """Convert VALUE to actual USD. Pre-2024-06-28 filings report in thousands."""
        df["VALUE"] = pd.to_numeric(df["VALUE"], errors="coerce").fillna(0).astype("int64")
        if period < _VALUE_IN_DOLLARS_FROM:
            logger.info("Period %s is pre-2024 — multiplying VALUE by 1000", period)
            df["VALUE"] = df["VALUE"] * 1000
        return df

    def _iter_chunks(self, df: pd.DataFrame) -> Iterator[pd.DataFrame]:
        """Yield successive CHUNK_SIZE slices of a DataFrame."""
        for start in range(0, len(df), self.CHUNK_SIZE):
            yield df.iloc[start : start + self.CHUNK_SIZE]

    @staticmethod
    def _map_holdings(
        df: pd.DataFrame, period_of_report: date, filing_date: date
    ) -> list[Sec13FHolding]:
        """Map a DataFrame chunk to a list of Sec13FHolding domain models."""
        records: list[Sec13FHolding] = []
        for _, row in df.iterrows():
            try:
                option_type = str(row.get("PUTCALL", "")).strip() or None
                records.append(Sec13FHolding(
                    accession_number     = str(row["ACCESSION_NUMBER"]).strip(),
                    cik                  = str(row["CIK"]).strip().zfill(10),
                    manager_name         = str(row["COMPANYNAME"]).strip(),
                    period_of_report     = period_of_report,
                    filing_date          = filing_date,
                    issuer_name          = str(row["NAMEOFISSUER"]).strip(),
                    class_title          = str(row["TITLEOFCLASS"]).strip(),
                    cusip                = str(row["CUSIP"]).strip(),
                    value_usd            = int(row["VALUE"]),
                    shares_or_prn_amount = int(pd.to_numeric(row["SSHPRNAMT"], errors="coerce") or 0),
                    shares_or_prn_type   = str(row["SSHPRNAMTTYPE"]).strip(),
                    option_type          = option_type,
                    investment_discretion= str(row["INVESTMENTDISCRETION"]).strip(),
                    voting_auth_sole     = int(pd.to_numeric(row.get("VOTINGAUTHORITY_SOLE", 0), errors="coerce") or 0),
                    voting_auth_shared   = int(pd.to_numeric(row.get("VOTINGAUTHORITY_SHARED", 0), errors="coerce") or 0),
                    voting_auth_none     = int(pd.to_numeric(row.get("VOTINGAUTHORITY_NONE", 0), errors="coerce") or 0),
                ))
            except Exception as exc:
                logger.warning("Skipping holding row (CUSIP=%s): %s", row.get("CUSIP"), exc)
        return records
