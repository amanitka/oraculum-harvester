"""SimFin data provider."""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Mapping, Optional

import pandas as pd
import simfin as sf

from common import (
    BalanceSheet,
    BalanceSheetTemplate,
    CashFlowStatement,
    CashFlowStatementTemplate,
    IncomeStatement,
    IncomeStatementTemplate,
    SharePrice,
    Ticker,
)
from common.config import config

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "simfin"
_REQUIRED_TICKER_COLUMNS: tuple[str, str] = ("Ticker", "Company Name")
_REQUIRED_SHARE_PRICE_COLUMNS: tuple[str, str] = ("Ticker", "Date")

_INCOME_LOADERS: Mapping[IncomeStatementTemplate, Callable[..., pd.DataFrame]] = {
    "general": sf.load_income,
    "banks": sf.load_income_banks,
    "insurance": sf.load_income_insurance,
}

_BALANCE_SHEET_LOADERS: Mapping[BalanceSheetTemplate, Callable[..., pd.DataFrame]] = {
    "general": sf.load_balance,
    "banks": sf.load_balance_banks,
    "insurance": sf.load_balance_insurance,
}

_CASH_FLOW_LOADERS: Mapping[CashFlowStatementTemplate, Callable[..., pd.DataFrame]] = {
    "general": sf.load_cashflow,
    "banks": sf.load_cashflow_banks,
    "insurance": sf.load_cashflow_insurance,
}

_pandas_patched = False


def _patch_pandas_for_simfin() -> None:
    """Pandas 2.0+ removed `date_parser`; keep legacy SimFin calls working.

    Idempotent: subsequent calls are no-ops so multiple `SimFinProvider`
    instances don't wrap the read_csv chain recursively.
    """
    global _pandas_patched
    if _pandas_patched:
        return
    original_read_csv = pd.read_csv

    def _patched(*args, **kwargs):
        kwargs.pop("date_parser", None)
        return original_read_csv(*args, **kwargs)

    pd.read_csv = _patched
    _pandas_patched = True


class SimFinProvider:
    """Fetches data from SimFin.

    Currently exposes `fetch_tickers`; future methods will add
    statements and derived ratios.
    """

    def __init__(self) -> None:
        cache_path = config.harvester_data_path / "simfin_cache"
        self._configure_sdk(cache_path)
        self._industry_map: Dict[int, Dict[str, Any]] = {}

    def fetch_tickers(self, market: str = "us") -> Iterator[Ticker]:
        """Yield validated `Ticker` records for the given market."""
        self._industry_map = self._load_industry_map()
        companies = self._load_companies(market)
        skipped_missing_required = 0
        skipped_invalid = 0
        published = 0
        for _, row in companies.iterrows():
            if not self._has_required_ticker_fields(row):
                skipped_missing_required += 1
                continue
            ticker = self._data_row_to_ticker(row)
            if ticker is not None:
                published += 1
                yield ticker
                continue
            skipped_invalid += 1
        logger.info(
            "Ticker load summary market=%s published=%d skipped_missing_required=%d skipped_invalid=%d",
            market,
            published,
            skipped_missing_required,
            skipped_invalid,
        )

    @staticmethod
    def _configure_sdk(cache_dir: Path) -> None:
        _patch_pandas_for_simfin()
        sf.set_api_key(config.simfin_api_key)
        cache_dir.mkdir(parents=True, exist_ok=True)
        sf.set_data_dir(str(cache_dir))

    @staticmethod
    def _load_industry_map() -> Dict[int, Dict[str, Any]]:
        logger.info("Loading industry metadata from SimFin")
        return sf.load_industries().to_dict(orient="index")

    @staticmethod
    def _load_companies(market: str) -> pd.DataFrame:
        logger.info("Loading companies for market=%s", market)
        return sf.load_companies(market=market).reset_index()

    def _data_row_to_ticker(self, row: pd.Series) -> Optional[Ticker]:
        symbol = row.get("Ticker", "Unknown")
        try:
            return Ticker.model_validate(self._build_raw_payload(row))
        except Exception as exc:  # noqa: BLE001 - vendor rows vary a lot
            logger.warning("Skipping ticker %s: %s", symbol, exc)
            return None

    @classmethod
    def _has_required_ticker_fields(cls, row: pd.Series) -> bool:
        for column in _REQUIRED_TICKER_COLUMNS:
            if cls._is_missing(row.get(column)):
                return False
        return True

    @staticmethod
    def _is_missing(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

    def _build_raw_payload(self, row: pd.Series) -> Dict[str, Any]:
        raw: Dict[str, Any] = row.to_dict()
        raw["provider_name"] = _PROVIDER_NAME
        self._enrich_with_industry(raw)
        return raw

    def _enrich_with_industry(self, raw: Dict[str, Any]) -> None:
        industry_id = self._coerce_industry_id(raw.get("IndustryId"))
        if industry_id is None:
            return
        metadata = self._industry_map.get(industry_id)
        if not metadata:
            return
        raw["industry_name"] = metadata.get("Industry")
        raw["sector_name"] = metadata.get("Sector")

    @staticmethod
    def _coerce_industry_id(value: Any) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, float) and math.isnan(value):
            return None
        try:
            return int(float(value))
        except (TypeError, ValueError):
            return None

    def fetch_share_prices(
        self,
        market: str,
        variant: str,
        from_date: Optional[date],
        safety_window_days: int,
    ) -> Iterator[SharePrice]:
        """Yield validated ``SharePrice`` records for the given market and date range."""
        logger.info(
            "Loading share prices variant=%s market=%s from_date=%s",
            variant,
            market,
            from_date,
        )
        df = sf.load_shareprices(variant=variant, market=market).reset_index()

        if from_date is not None:
            date_series = pd.to_datetime(df["Date"], errors="coerce")
            cutoff = pd.Timestamp(from_date - timedelta(days=safety_window_days))
            df = df[date_series >= cutoff]

        extracted_at = datetime.now(timezone.utc)
        published = 0
        skipped_missing_required = 0
        skipped_invalid = 0
        for _, row in df.iterrows():
            if not self._has_required_share_price_fields(row):
                skipped_missing_required += 1
                continue

            price = self._data_row_to_share_price(row, market, extracted_at)
            if price is not None:
                yield price
                published += 1
            else:
                skipped_invalid += 1

        logger.info(
            "Share price load summary market=%s variant=%s published=%d skipped_missing_required=%d skipped_invalid=%d",
            market,
            variant,
            published,
            skipped_missing_required,
            skipped_invalid,
        )

    @classmethod
    def _has_required_share_price_fields(cls, row: pd.Series) -> bool:
        for column in _REQUIRED_SHARE_PRICE_COLUMNS:
            if cls._is_missing(row.get(column)):
                return False
        return True

    @staticmethod
    def _data_row_to_share_price(
        row: pd.Series,
        market: str,
        extracted_at: datetime,
    ) -> Optional[SharePrice]:
        symbol = row.get("Ticker", "Unknown")
        try:
            payload: Dict[str, Any] = row.to_dict()
            payload["market"] = market
            payload["extracted_at"] = extracted_at
            return SharePrice.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - vendor rows vary a lot
            logger.warning("Skipping share price row ticker=%s: %s", symbol, exc)
            return None

    def fetch_income(
        self,
        template: IncomeStatementTemplate,
        variant: str,
        market: str,
    ) -> Iterator[IncomeStatement]:
        """Yield validated `IncomeStatement` rows for one SimFin industry template."""
        income_data = self._load_income(template, variant, market)
        extracted_at = datetime.now(timezone.utc)
        for _, row in income_data.iterrows():
            statement = self._data_row_to_income(row, template, variant, extracted_at)
            if statement is not None:
                yield statement

    @staticmethod
    def _load_income(
        template: IncomeStatementTemplate, variant: str, market: str
    ) -> pd.DataFrame:
        loader = _INCOME_LOADERS[template]
        logger.info(
            "Loading income template=%s variant=%s market=%s",
            template,
            variant,
            market,
        )
        return loader(variant=variant, market=market).reset_index()

    @staticmethod
    def _data_row_to_income(
        row: pd.Series,
        template: IncomeStatementTemplate,
        variant: str,
        extracted_at: datetime,
    ) -> Optional[IncomeStatement]:
        symbol = row.get("Ticker", "Unknown")
        try:
            payload: Dict[str, Any] = row.to_dict()
            payload["template"] = template
            payload["variant"] = variant
            payload["extracted_at"] = extracted_at
            return IncomeStatement.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - vendor rows vary a lot
            logger.warning(
                "Skipping income row template=%s ticker=%s: %s", template, symbol, exc
            )
            return None

    def fetch_balance_sheet(
        self,
        template: BalanceSheetTemplate,
        variant: str,
        market: str,
    ) -> Iterator[BalanceSheet]:
        """Yield validated `BalanceSheet` rows for one SimFin industry template."""
        balance_data = self._load_balance_sheet(template, variant, market)
        extracted_at = datetime.now(timezone.utc)
        for _, row in balance_data.iterrows():
            statement = self._data_row_to_balance_sheet(
                row,
                template,
                variant,
                extracted_at,
            )
            if statement is not None:
                yield statement

    @staticmethod
    def _load_balance_sheet(
        template: BalanceSheetTemplate, variant: str, market: str
    ) -> pd.DataFrame:
        loader = _BALANCE_SHEET_LOADERS[template]
        logger.info(
            "Loading balance sheet template=%s variant=%s market=%s",
            template,
            variant,
            market,
        )
        return loader(variant=variant, market=market).reset_index()

    @staticmethod
    def _data_row_to_balance_sheet(
        row: pd.Series,
        template: BalanceSheetTemplate,
        variant: str,
        extracted_at: datetime,
    ) -> Optional[BalanceSheet]:
        symbol = row.get("Ticker", "Unknown")
        try:
            payload: Dict[str, Any] = row.to_dict()
            payload["template"] = template
            payload["variant"] = variant
            payload["extracted_at"] = extracted_at
            return BalanceSheet.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - vendor rows vary a lot
            logger.warning(
                "Skipping balance sheet row template=%s ticker=%s: %s",
                template,
                symbol,
                exc,
            )
            return None

    def fetch_cash_flow_statement(
        self,
        template: CashFlowStatementTemplate,
        variant: str,
        market: str,
    ) -> Iterator[CashFlowStatement]:
        """Yield validated `CashFlowStatement` rows for one SimFin industry template."""
        cash_flow_data = self._load_cash_flow_statement(template, variant, market)
        extracted_at = datetime.now(timezone.utc)
        for _, row in cash_flow_data.iterrows():
            statement = self._data_row_to_cash_flow_statement(
                row,
                template,
                variant,
                extracted_at,
            )
            if statement is not None:
                yield statement

    @staticmethod
    def _load_cash_flow_statement(
        template: CashFlowStatementTemplate, variant: str, market: str
    ) -> pd.DataFrame:
        loader = _CASH_FLOW_LOADERS[template]
        logger.info(
            "Loading cash flow statement template=%s variant=%s market=%s",
            template,
            variant,
            market,
        )
        return loader(variant=variant, market=market).reset_index()

    @staticmethod
    def _data_row_to_cash_flow_statement(
        row: pd.Series,
        template: CashFlowStatementTemplate,
        variant: str,
        extracted_at: datetime,
    ) -> Optional[CashFlowStatement]:
        symbol = row.get("Ticker", "Unknown")
        try:
            payload: Dict[str, Any] = row.to_dict()
            payload["template"] = template
            payload["variant"] = variant
            payload["extracted_at"] = extracted_at
            return CashFlowStatement.model_validate(payload)
        except Exception as exc:  # noqa: BLE001 - vendor rows vary a lot
            logger.warning(
                "Skipping cash flow row template=%s ticker=%s: %s",
                template,
                symbol,
                exc,
            )
            return None
