"""SimFin data provider.

Wraps the ``simfin`` SDK to provide domain-specific objects and
error handling.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional

import pandas as pd
import simfin as sf
from pydantic import ValidationError

from common.config import config
from common.domain.balance_sheet import BalanceSheet, BalanceSheetTemplate
from common.domain.cash_flow_statement import (
    CashFlowStatement,
    CashFlowStatementTemplate,
)
from common.domain.company import Company
from common.domain.income_statement import IncomeStatement, IncomeStatementTemplate
from common.domain.industry import Industry
from common.domain.market import Market
from common.domain.share_price import SharePrice

logger = logging.getLogger(__name__)

_COMPANY_TICKER_COLUMNS = ("Ticker", "index", "level_0", "Symbol", "symbol")
_COMPANY_ID_COLUMNS = ("SimFinId", "level_1", "simfin_id", "SimFin ID")
_COMPANY_CURRENCY_COLUMNS = ("Currency", "Price Currency", "currency")
_DEFAULT_CURRENCY_BY_MARKET = {"us": "USD"}
_REQUIRED_SHARE_PRICE_COLUMNS = ("Ticker", "SimFinId", "Date", "Close")
_REQUIRED_STATEMENT_COLUMNS = (
    "Ticker",
    "SimFinId",
    "Currency",
    "Fiscal Year",
    "Fiscal Period",
    "Report Date",
    "Publish Date",
)
_SIMFIN_INDUSTRY_ID_KEY = "IndustryId"
_SIMFIN_SECTOR_KEY = "Sector"
_SIMFIN_INDUSTRY_NAME_KEY = "Industry"
_SIMFIN_MARKET_ID_KEY = "MarketId"
_SIMFIN_MARKET_NAME_KEY = "Market Name"
_SIMFIN_CURRENCY_KEY = "Currency"
_INCOME_LOADERS: dict[IncomeStatementTemplate, Callable[..., pd.DataFrame]] = {
    "banks": sf.load_income_banks,
    "insurance": sf.load_income_insurance,
    "general": sf.load_income,
}
_BALANCE_SHEET_LOADERS: dict[BalanceSheetTemplate, Callable[..., pd.DataFrame]] = {
    "banks": sf.load_balance_banks,
    "insurance": sf.load_balance_insurance,
    "general": sf.load_balance,
}
_CASH_FLOW_LOADERS: dict[CashFlowStatementTemplate, Callable[..., pd.DataFrame]] = {
    "banks": sf.load_cashflow_banks,
    "insurance": sf.load_cashflow_insurance,
    "general": sf.load_cashflow,
}


def _patch_pandas_for_simfin() -> None:
    """Remove the ``date_parser`` kwarg that SimFin passes to Pandas 2+."""
    original = pd.read_csv

    def _patched(*args: Any, **kwargs: Any) -> pd.DataFrame:
        kwargs.pop("date_parser", None)
        return original(*args, **kwargs)

    pd.read_csv = _patched  # type: ignore[assignment]


class SimFinProvider:
    """Fetches data from SimFin.

    Currently exposes `fetch_companies`; future methods will add
    statements and derived ratios.
    """

    def __init__(self) -> None:
        cache_path = config.harvester_data_directory / "simfin"
        self._configure_sdk(cache_path)
        self._industry_map: Dict[int, Dict[str, Any]] = {}

    def fetch_companies(self, market: str = "us") -> Iterator[Company]:
        """Yield validated ``Company`` records for the given market."""
        self._industry_map = self._load_industry_map()
        companies = self._load_companies(market)
        skipped_missing_required = 0
        skipped_invalid = 0
        published = 0
        for _, row in companies.iterrows():
            if not self._has_required_company_fields(row):
                skipped_missing_required += 1
                continue
            company = self._data_row_to_company(row, market)
            if company is not None:
                published += 1
                yield company
                continue
            skipped_invalid += 1
        logger.info(
            "Company load summary market=%s published=%d skipped_missing_required=%d skipped_invalid=%d",
            market,
            published,
            skipped_missing_required,
            skipped_invalid,
        )

    def fetch_industries(self) -> Iterator[Industry]:
        """Yield validated `Industry` records."""
        logger.info("Loading industries from SimFin")
        df = sf.load_industries(refresh_days=config.simfin_refresh_days).reset_index()
        extracted_at = datetime.now(timezone.utc)

        published = 0
        skipped = 0

        for _, row in df.iterrows():
            industry = self._data_row_to_industry(row, extracted_at)
            if industry:
                published += 1
                yield industry
            else:
                skipped += 1

        logger.info("Industry load summary: published=%d skipped=%d", published, skipped)

    @staticmethod
    def _data_row_to_industry(row: pd.Series, extracted_at: datetime) -> Industry | None:
        """Convert a data row to an Industry record."""
        try:
            source_payload = row.to_dict()
            industry_name = source_payload.get(_SIMFIN_INDUSTRY_NAME_KEY)
            payload = {
                "industryId": source_payload.get(_SIMFIN_INDUSTRY_ID_KEY),
                "sectorName": source_payload.get(_SIMFIN_SECTOR_KEY),
                "industryName": industry_name,
                "extractedAt": extracted_at,
            }
            return Industry.model_validate(payload)
        except Exception as exc:
            logger.warning(
                "Skipping industry row %s: %s",
                row.get(_SIMFIN_INDUSTRY_ID_KEY, "Unknown"),
                exc,
            )
            return None

    def fetch_markets(self) -> Iterator[Market]:
        """Yield validated `Market` records."""
        logger.info("Loading markets from SimFin")
        df = sf.load_markets(refresh_days=config.simfin_refresh_days).reset_index()
        extracted_at = datetime.now(timezone.utc)

        published = 0
        skipped = 0

        for _, row in df.iterrows():
            market = self._data_row_to_market(row, extracted_at)
            if market:
                published += 1
                yield market
            else:
                skipped += 1

        logger.info("Market load summary: published=%d skipped=%d", published, skipped)

    @staticmethod
    def _data_row_to_market(row: pd.Series, extracted_at: datetime) -> Market | None:
        """Convert a data row to a Market record."""
        try:
            source_payload = row.to_dict()
            payload = {
                "marketId": source_payload.get(_SIMFIN_MARKET_ID_KEY),
                "marketName": source_payload.get(_SIMFIN_MARKET_NAME_KEY),
                "currency": source_payload.get(_SIMFIN_CURRENCY_KEY),
                "extractedAt": extracted_at,
            }
            return Market.model_validate(payload)
        except Exception as exc:
            logger.warning(
                "Skipping market row %s: %s",
                row.get(_SIMFIN_MARKET_ID_KEY, "Unknown"),
                exc,
            )
            return None

    @staticmethod
    def _configure_sdk(cache_dir: Path) -> None:
        _patch_pandas_for_simfin()
        sf.set_api_key(config.simfin_api_key)
        cache_dir.mkdir(parents=True, exist_ok=True)
        sf.set_data_dir(str(cache_dir))

    @staticmethod
    def _load_industry_map() -> Dict[int, Dict[str, Any]]:
        logger.info("Loading industry metadata from SimFin")
        from pandas.errors import EmptyDataError

        try:
            # Added refresh_days parameter from config
            return sf.load_industries(refresh_days=config.simfin_refresh_days).to_dict(orient="index")
        except EmptyDataError as exc:
            logger.warning("Skipping empty industry dataset: %s", exc)
            return {}

    @staticmethod
    def _load_companies(market: str) -> pd.DataFrame:
        logger.info("Loading companies for market=%s", market)
        from pandas.errors import EmptyDataError

        try:
            # Added refresh_days parameter from config
            return sf.load_companies(market=market, refresh_days=config.simfin_refresh_days).reset_index()
        except EmptyDataError as exc:
            logger.warning("Skipping empty companies dataset for market=%s: %s", market, exc)
            return pd.DataFrame()

    def _data_row_to_company(self, row: pd.Series, market: str) -> Optional[Company]:
        symbol = self._first_present_value(row, _COMPANY_TICKER_COLUMNS) or "Unknown"
        try:
            return Company.model_validate(self._build_raw_payload(row, market))
        except Exception as exc:  # noqa: BLE001 - vendor rows vary a lot
            logger.warning("Skipping company %s: %s", symbol, exc)
            return None

    @classmethod
    def _has_required_company_fields(cls, row: pd.Series) -> bool:
        ticker = cls._first_present_value(row, _COMPANY_TICKER_COLUMNS)
        company_id = cls._first_present_value(row, _COMPANY_ID_COLUMNS)
        company_name = row.get("Company Name")
        return not (cls._is_missing(ticker) or cls._is_missing(company_id) or cls._is_missing(company_name))

    @staticmethod
    def _is_missing(value: Any) -> bool:
        if value is None:
            return True
        if isinstance(value, float) and math.isnan(value):
            return True
        if isinstance(value, str) and not value.strip():
            return True
        return False

    @classmethod
    def _first_present_value(
        cls,
        payload: pd.Series | Dict[str, Any],
        columns: tuple[str, ...],
    ) -> Any:
        for column in columns:
            value = payload.get(column)
            if not cls._is_missing(value):
                return value
        return None

    def _build_raw_payload(self, row: pd.Series, market: str) -> Dict[str, Any]:
        raw: Dict[str, Any] = row.to_dict()
        raw["Ticker"] = self._first_present_value(raw, _COMPANY_TICKER_COLUMNS)
        raw["SimFinId"] = self._first_present_value(raw, _COMPANY_ID_COLUMNS)
        raw["Currency"] = self._first_present_value(raw, _COMPANY_CURRENCY_COLUMNS)
        if self._is_missing(raw.get("Currency")):
            fallback_currency = _DEFAULT_CURRENCY_BY_MARKET.get(market.lower())
            if fallback_currency is not None:
                raw["Currency"] = fallback_currency
        raw["market"] = market
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
        except TypeError, ValueError:
            return None

    def fetch_share_prices(self, market: str, variant: str, from_date: Optional[date]) -> Iterator[List[SharePrice]]:
        """Yield lists of validated ``SharePrice`` records for the given market and date range in chunks."""
        logger.info(
            "Loading share prices variant=%s market=%s from_date=%s",
            variant,
            market,
            from_date,
        )

        # SimFin's load() does not support chunksize, so we load the DataFrame first.
        # The memory spike usually comes from millions of Python Pydantic objects,
        # not the raw Pandas DataFrame. We'll chunk the output yielding instead.
        # Added refresh_days parameter from config
        from pandas.errors import EmptyDataError

        try:
            df = sf.load_shareprices(
                variant=variant, market=market, refresh_days=config.simfin_refresh_days
            ).reset_index()
        except EmptyDataError as exc:
            logger.warning("Skipping empty share prices dataset variant=%s market=%s: %s", variant, market, exc)
            df = pd.DataFrame()

        if df.empty:
            return

        if from_date is not None:
            date_series = pd.to_datetime(df["Date"], errors="coerce")
            cutoff = pd.Timestamp(from_date)
            if date_series.dt.tz is not None:
                cutoff = cutoff.tz_localize(date_series.dt.tz)
            df = df[date_series >= cutoff]

        extracted_at = datetime.now(timezone.utc)

        total_published = 0
        total_skipped_missing = 0
        total_skipped_invalid = 0

        chunk_size = config.simfin_chunk_size
        chunk_results = []

        for _, row in df.iterrows():
            if not self._has_required_share_price_fields(row):
                total_skipped_missing += 1
                continue

            price = self._data_row_to_share_price(row, market, extracted_at)
            if price is not None:
                chunk_results.append(price)
                total_published += 1
            else:
                total_skipped_invalid += 1

            # Yield when chunk reaches target size
            if len(chunk_results) >= chunk_size:
                yield chunk_results
                chunk_results = []

        # Yield any remaining records
        if chunk_results:
            yield chunk_results

        logger.info(
            "Share price load summary market=%s variant=%s published=%d skipped_missing_required=%d skipped_invalid=%d",
            market,
            variant,
            total_published,
            total_skipped_missing,
            total_skipped_invalid,
        )

        # Force aggressive memory cleanup to return memory to the OS as much as possible
        del df
        from common.memory import release_memory
        release_memory()

    @classmethod
    def _has_required_share_price_fields(cls, row: pd.Series) -> bool:
        for column in _REQUIRED_SHARE_PRICE_COLUMNS:
            if cls._is_missing(row.get(column)):
                return False
        return True

    @classmethod
    def _has_required_statement_fields(cls, row: pd.Series) -> bool:
        for column in _REQUIRED_STATEMENT_COLUMNS:
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
        published = 0
        skipped_missing_required = 0
        skipped_invalid = 0
        for _, row in income_data.iterrows():
            if not self._has_required_statement_fields(row):
                skipped_missing_required += 1
                continue
            statement = self._data_row_to_income(
                row,
                template,
                variant,
                market,
                extracted_at,
            )
            if statement is not None:
                published += 1
                yield statement
            else:
                skipped_invalid += 1
        logger.info(
            "Income load summary template=%s variant=%s market=%s published=%d skipped_missing_required=%d skipped_invalid=%d",
            template,
            variant,
            market,
            published,
            skipped_missing_required,
            skipped_invalid,
        )

    @staticmethod
    def _load_income(template: IncomeStatementTemplate, variant: str, market: str) -> pd.DataFrame:
        loader = _INCOME_LOADERS[template]
        logger.info(
            "Loading income template=%s variant=%s market=%s",
            template,
            variant,
            market,
        )
        from pandas.errors import EmptyDataError

        try:
            # Added refresh_days parameter from config
            return loader(variant=variant, market=market, refresh_days=config.simfin_refresh_days).reset_index()
        except EmptyDataError as exc:
            logger.warning(
                "Skipping empty income dataset template=%s variant=%s market=%s: %s",
                template,
                variant,
                market,
                exc,
            )
            return pd.DataFrame()

    @staticmethod
    def _data_row_to_income(
        row: pd.Series,
        template: IncomeStatementTemplate,
        variant: str,
        market: str,
        extracted_at: datetime,
    ) -> Optional[IncomeStatement]:
        symbol = row.get("Ticker", "Unknown")
        try:
            payload: Dict[str, Any] = row.to_dict()
            model_input = payload.copy()
            model_input["template"] = template
            model_input["variant"] = variant
            model_input["market"] = market
            model_input["extracted_at"] = extracted_at
            model_input["statement_data"] = payload
            return IncomeStatement.model_validate(model_input)
        except (ValidationError, TypeError) as exc:
            logger.warning("Skipping income row template=%s ticker=%s: %s", template, symbol, exc)
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
        published = 0
        skipped_missing_required = 0
        skipped_invalid = 0
        for _, row in balance_data.iterrows():
            if not self._has_required_statement_fields(row):
                skipped_missing_required += 1
                continue
            statement = self._data_row_to_balance_sheet(
                row,
                template,
                variant,
                market,
                extracted_at,
            )
            if statement is not None:
                published += 1
                yield statement
            else:
                skipped_invalid += 1
        logger.info(
            "Balance sheet load summary template=%s variant=%s market=%s published=%d skipped_missing_required=%d skipped_invalid=%d",
            template,
            variant,
            market,
            published,
            skipped_missing_required,
            skipped_invalid,
        )

    @staticmethod
    def _load_balance_sheet(template: BalanceSheetTemplate, variant: str, market: str) -> pd.DataFrame:
        loader = _BALANCE_SHEET_LOADERS[template]
        logger.info(
            "Loading balance sheet template=%s variant=%s market=%s",
            template,
            variant,
            market,
        )
        from pandas.errors import EmptyDataError

        try:
            # Added refresh_days parameter from config
            return loader(variant=variant, market=market, refresh_days=config.simfin_refresh_days).reset_index()
        except EmptyDataError as exc:
            logger.warning(
                "Skipping empty balance sheet dataset template=%s variant=%s market=%s: %s",
                template,
                variant,
                market,
                exc,
            )
            return pd.DataFrame()

    @staticmethod
    def _data_row_to_balance_sheet(
        row: pd.Series,
        template: BalanceSheetTemplate,
        variant: str,
        market: str,
        extracted_at: datetime,
    ) -> Optional[BalanceSheet]:
        symbol = row.get("Ticker", "Unknown")
        try:
            payload: Dict[str, Any] = row.to_dict()
            model_input = payload.copy()
            model_input["template"] = template
            model_input["variant"] = variant
            model_input["market"] = market
            model_input["extracted_at"] = extracted_at
            model_input["statement_data"] = payload
            return BalanceSheet.model_validate(model_input)
        except (ValidationError, TypeError) as exc:
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
        published = 0
        skipped_missing_required = 0
        skipped_invalid = 0
        for _, row in cash_flow_data.iterrows():
            if not self._has_required_statement_fields(row):
                skipped_missing_required += 1
                continue
            statement = self._data_row_to_cash_flow_statement(
                row,
                template,
                variant,
                market,
                extracted_at,
            )
            if statement is not None:
                published += 1
                yield statement
            else:
                skipped_invalid += 1
        logger.info(
            "Cash flow load summary template=%s variant=%s market=%s published=%d skipped_missing_required=%d skipped_invalid=%d",
            template,
            variant,
            market,
            published,
            skipped_missing_required,
            skipped_invalid,
        )

    @staticmethod
    def _load_cash_flow_statement(template: CashFlowStatementTemplate, variant: str, market: str) -> pd.DataFrame:
        loader = _CASH_FLOW_LOADERS[template]
        logger.info(
            "Loading cash flow statement template=%s variant=%s market=%s",
            template,
            variant,
            market,
        )
        from pandas.errors import EmptyDataError

        try:
            # Added refresh_days parameter from config
            return loader(variant=variant, market=market, refresh_days=config.simfin_refresh_days).reset_index()
        except EmptyDataError as exc:
            logger.warning(
                "Skipping empty cash flow statement dataset template=%s variant=%s market=%s: %s",
                template,
                variant,
                market,
                exc,
            )
            return pd.DataFrame()

    @staticmethod
    def _data_row_to_cash_flow_statement(
        row: pd.Series,
        template: CashFlowStatementTemplate,
        variant: str,
        market: str,
        extracted_at: datetime,
    ) -> Optional[CashFlowStatement]:
        symbol = row.get("Ticker", "Unknown")
        try:
            payload: Dict[str, Any] = row.to_dict()
            model_input = payload.copy()
            model_input["template"] = template
            model_input["variant"] = variant
            model_input["market"] = market
            model_input["extracted_at"] = extracted_at
            model_input["statement_data"] = payload
            return CashFlowStatement.model_validate(model_input)
        except (ValidationError, TypeError) as exc:
            logger.warning(
                "Skipping cash flow row template=%s ticker=%s: %s",
                template,
                symbol,
                exc,
            )
            return None
