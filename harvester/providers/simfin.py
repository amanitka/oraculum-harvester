"""SimFin data provider."""
from __future__ import annotations

import logging
import math
from pathlib import Path
from typing import Any, Dict, Iterator, Optional

import pandas as pd
import simfin as sf

from common import Ticker
from common.config import config

logger = logging.getLogger(__name__)

_DEFAULT_CACHE_DIR = Path("./data/simfin_cache")
_PROVIDER_NAME = "simfin"

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

    def __init__(self, cache_dir: Path = _DEFAULT_CACHE_DIR) -> None:
        self._configure_sdk(cache_dir)
        self._industry_map: Dict[int, Dict[str, Any]] = {}

    def fetch_tickers(self, market: str = "us") -> Iterator[Ticker]:
        """Yield validated `Ticker` records for the given market."""
        self._industry_map = self._load_industry_map()
        companies = self._load_companies(market)
        for _, row in companies.iterrows():
            ticker = self._row_to_ticker(row)
            if ticker is not None:
                yield ticker

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

    def _row_to_ticker(self, row: pd.Series) -> Optional[Ticker]:
        symbol = row.get("Ticker", "Unknown")
        try:
            return Ticker.model_validate(self._build_raw_payload(row))
        except Exception as exc:  # noqa: BLE001 - vendor rows vary a lot
            logger.warning("Skipping ticker %s: %s", symbol, exc)
            return None

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
