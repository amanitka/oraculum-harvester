"""SimFin market data provider."""

import logging
from datetime import datetime, timezone
from typing import Iterator

import pandas as pd
import simfin as sf

from common.config import config
from common.domain.market import Market

logger = logging.getLogger(__name__)

SIMFIN_MARKET_ID_KEY = "MarketId"
SIMFIN_MARKET_NAME_KEY = "Market Name"
SIMFIN_CURRENCY_KEY = "Currency"


class MarketProvider:
    """Fetches market metadata from SimFin."""

    def __init__(self) -> None:
        cache_path = config.harvester_data_path / "simfin_cache"
        sf.set_api_key(config.simfin_api_key)
        cache_path.mkdir(parents=True, exist_ok=True)
        sf.set_data_dir(str(cache_path))

    def fetch_markets(self) -> Iterator[Market]:
        """Yield validated `Market` records."""
        logger.info("Loading markets from SimFin")
        # Added refresh_days parameter from config
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

        logger.info(f"Market load summary: published={published} skipped={skipped}")

    @staticmethod
    def _data_row_to_market(row: pd.Series, extracted_at: datetime) -> Market | None:
        try:
            source_payload = row.to_dict()
            payload = {
                "marketId": source_payload.get(SIMFIN_MARKET_ID_KEY),
                "marketName": source_payload.get(SIMFIN_MARKET_NAME_KEY),
                "currency": source_payload.get(SIMFIN_CURRENCY_KEY),
                "extractedAt": extracted_at,
            }
            return Market.model_validate(payload)
        except Exception as exc:
            logger.warning(f"Skipping market row {row.get(SIMFIN_MARKET_ID_KEY, 'Unknown')}: {exc}")
            return None
