"""SimFin data provider.

Wraps the ``simfin`` SDK to provide domain-specific objects and
error handling.
"""

from __future__ import annotations

import logging
import math
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, Optional

import pandas as pd
import simfin as sf
from simfin.names import (
    ACC_NOTES_RECV,
    CAPEX,
    CASH_EQUIV_ST_INVEST,
    DEPR_AMOR,
    INCOME_TAX,
    INTEREST_EXP_NET,
    INVENTORIES,
    NET_CASH_OPS,
    NET_INCOME,
    REVENUE,
    SHARES_BASIC,
    SHARES_DILUTED,
    TOTAL_CUR_ASSETS,
    TOTAL_EQUITY,
    TOTAL_LIABILITIES,
)
from pydantic import ValidationError

from common.config import config
from common.domain.balance_sheet import BalanceSheet, BalanceSheetTemplate
from common.domain.cash_flow_statement import (
    CashFlowStatement,
    CashFlowStatementTemplate,
)
from common.domain.derived import Derived, DerivedTemplate
from common.domain.income_statement import IncomeStatement, IncomeStatementTemplate
from common.domain.share_price import SharePrice
from common.domain.ticker import Ticker

logger = logging.getLogger(__name__)

_PROVIDER_NAME = "simfin"
_REQUIRED_TICKER_COLUMNS = ("Ticker", "Company Name")
_REQUIRED_SHARE_PRICE_COLUMNS = ("Ticker", "Date", "Close")
_REQUIRED_STATEMENT_COLUMNS = (
    "Ticker",
    "SimFinId",
    "Currency",
    "Fiscal Year",
    "Fiscal Period",
    "Report Date",
    "Publish Date",
)
_DERIVED_JOIN_COLUMNS = (
    "Ticker",
    "SimFinId",
    "Currency",
    "Fiscal Year",
    "Fiscal Period",
    "Report Date",
    "Publish Date",
    "Restated Date",
)

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
            statement = self._data_row_to_income(row, template, variant, extracted_at)
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
            model_input = payload.copy()
            model_input["template"] = template
            model_input["variant"] = variant
            model_input["extracted_at"] = extracted_at
            model_input["payload"] = payload
            return IncomeStatement.model_validate(model_input)
        except (ValidationError, TypeError) as exc:
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
            model_input = payload.copy()
            model_input["template"] = template
            model_input["variant"] = variant
            model_input["extracted_at"] = extracted_at
            model_input["payload"] = payload
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
            model_input = payload.copy()
            model_input["template"] = template
            model_input["variant"] = variant
            model_input["extracted_at"] = extracted_at
            model_input["payload"] = payload
            return CashFlowStatement.model_validate(model_input)
        except (ValidationError, TypeError) as exc:
            logger.warning(
                "Skipping cash flow row template=%s ticker=%s: %s",
                template,
                symbol,
                exc,
            )
            return None

    def fetch_derived(
            self,
            template: DerivedTemplate,
            variant: str,
            market: str,
    ) -> Iterator[Derived]:
        """Yield validated `Derived` rows for one SimFin industry template."""
        extracted_at = datetime.now(timezone.utc)
        frame = self._build_derived_frame(template, variant, market, extracted_at)
        published = 0
        skipped_invalid = 0
        for _, row in frame.iterrows():
            derived = self._data_row_to_derived(row, template)
            if derived is not None:
                published += 1
                yield derived
                continue
            skipped_invalid += 1
        logger.info(
            "Derived load summary template=%s variant=%s market=%s published=%d skipped_invalid=%d",
            template,
            variant,
            market,
            published,
            skipped_invalid,
        )

    def _build_derived_frame(
            self,
            template: DerivedTemplate,
            variant: str,
            market: str,
            extracted_at: datetime,
    ) -> pd.DataFrame:
        """Build the parquet-ready derived metrics frame."""
        income_data = self._load_income(template, variant, market)
        balance_data = self._load_balance_sheet(template, variant, market)
        cash_flow_data = self._load_cash_flow_statement(template, variant, market)
        merged = self._merge_derived_sources(income_data, balance_data, cash_flow_data)
        return self._calculate_derived_metrics(merged, template, variant, extracted_at)

    @classmethod
    def _merge_derived_sources(
            cls,
            income_data: pd.DataFrame,
            balance_data: pd.DataFrame,
            cash_flow_data: pd.DataFrame,
    ) -> pd.DataFrame:
        """Join income, balance sheet, and cash flow rows by statement identity."""
        income = cls._prepare_derived_source(income_data)
        balance = cls._prepare_derived_source(balance_data)
        cash_flow = cls._prepare_derived_source(cash_flow_data)
        with_balance = income.merge(balance, on=list(_DERIVED_JOIN_COLUMNS), how="inner")
        return with_balance.merge(
            cash_flow,
            on=list(_DERIVED_JOIN_COLUMNS),
            how="inner",
            suffixes=("", "_cash"),
        )

    @staticmethod
    def _prepare_derived_source(data: pd.DataFrame) -> pd.DataFrame:
        """Ensure one SimFin source frame can participate in derived joins."""
        prepared = data.copy()
        if "Restated Date" not in prepared.columns:
            prepared["Restated Date"] = None
        missing = [column for column in _DERIVED_JOIN_COLUMNS if column not in prepared.columns]
        if missing:
            raise ValueError(
                "Cannot calculate derived metrics; missing join columns: "
                + ", ".join(missing)
            )
        prepared["Restated Date"] = prepared["Restated Date"].astype("object").where(
            pd.notna(prepared["Restated Date"]), None
        )
        return prepared

    @classmethod
    def _calculate_derived_metrics(
            cls,
            data: pd.DataFrame,
            template: DerivedTemplate,
            variant: str,
            extracted_at: datetime,
    ) -> pd.DataFrame:
        """Calculate all derived metric columns from merged statement rows."""
        net_income = cls._numeric_column(data, NET_INCOME)
        revenue = cls._numeric_column(data, REVENUE)
        total_equity = cls._numeric_column(data, TOTAL_EQUITY)
        return pd.DataFrame(
            {
                "template": template,
                "variant": variant,
                "ticker": data["Ticker"],
                "simfin_id": data["SimFinId"],
                "currency": data["Currency"],
                "fiscal_year": data["Fiscal Year"],
                "fiscal_period": data["Fiscal Period"],
                "report_date": data["Report Date"],
                "publish_date": data["Publish Date"],
                "restated_date": data["Restated Date"],
                "extracted_at": extracted_at,
                "ebitda": cls._calculate_ebitda(data),
                "free_cash_flow": cls._calculate_free_cash_flow(data),
                "ncav": cls._calculate_ncav(data),
                "net_net_working_capital": cls._calculate_net_net_working_capital(data),
                "shares_stabilized": cls._calculate_shares_stabilized(data),
                "return_on_equity": cls._safe_ratio(net_income, total_equity),
                "net_margin": cls._safe_ratio(net_income, revenue),
                "revenue": revenue,
                "net_income": net_income,
            }
        )

    @classmethod
    def _calculate_ebitda(cls, data: pd.DataFrame) -> pd.Series:
        """Calculate EBITDA from income and cash flow statement columns."""
        return (
            cls._zero_filled_numeric_column(data, NET_INCOME)
            - cls._zero_filled_numeric_column(data, INTEREST_EXP_NET)
            - cls._zero_filled_numeric_column(data, INCOME_TAX)
            + cls._zero_filled_numeric_column(data, DEPR_AMOR)
        )

    @classmethod
    def _calculate_free_cash_flow(cls, data: pd.DataFrame) -> pd.Series:
        """Calculate free cash flow from operating cash flow and capex."""
        return cls._zero_filled_numeric_column(
            data, NET_CASH_OPS
        ) + cls._zero_filled_numeric_column(data, CAPEX)

    @classmethod
    def _calculate_ncav(cls, data: pd.DataFrame) -> pd.Series:
        """Calculate net current asset value."""
        return cls._numeric_column(data, TOTAL_CUR_ASSETS) - cls._numeric_column(
            data, TOTAL_LIABILITIES
        )

    @classmethod
    def _calculate_net_net_working_capital(cls, data: pd.DataFrame) -> pd.Series:
        """Calculate net-net working capital."""
        return (
            cls._zero_filled_numeric_column(data, CASH_EQUIV_ST_INVEST)
            + cls._zero_filled_numeric_column(data, ACC_NOTES_RECV) * 0.75
            + cls._zero_filled_numeric_column(data, INVENTORIES) * 0.5
            - cls._zero_filled_numeric_column(data, TOTAL_LIABILITIES)
        )

    @classmethod
    def _calculate_shares_stabilized(cls, data: pd.DataFrame) -> pd.Series:
        """Return diluted shares with basic shares as fallback."""
        return cls._numeric_column(data, SHARES_DILUTED).fillna(
            cls._numeric_column(data, SHARES_BASIC)
        )

    @staticmethod
    def _numeric_column(data: pd.DataFrame, column: str) -> pd.Series:
        """Return one numeric source column, coercing missing values."""
        if column not in data.columns:
            return pd.Series(pd.NA, index=data.index, dtype="Float64")
        return pd.to_numeric(data[column], errors="coerce")

    @classmethod
    def _zero_filled_numeric_column(cls, data: pd.DataFrame, column: str) -> pd.Series:
        """Return one numeric source column with missing values set to zero."""
        return cls._numeric_column(data, column).fillna(0)

    @staticmethod
    def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
        """Divide two series while suppressing zero-denominator infinities."""
        safe_denominator = denominator.mask(denominator == 0)
        return (numerator / safe_denominator).replace([math.inf, -math.inf], pd.NA)

    @staticmethod
    def _data_row_to_derived(
            row: pd.Series,
            template: DerivedTemplate,
    ) -> Optional[Derived]:
        """Validate one calculated derived row."""
        symbol = row.get("ticker", "Unknown")
        try:
            return Derived.model_validate(row.to_dict())
        except (ValidationError, TypeError) as exc:
            logger.warning(
                "Skipping derived row template=%s ticker=%s: %s", template, symbol, exc
            )
            return None
