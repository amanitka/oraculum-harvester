"""SimFin market data provider."""

import logging
from datetime import datetime, timezone
from typing import Iterator

import simfin as sf
import pandas as pd

from common.config import config
from common.domain.market import Market

logger = logging.getLogger(__name__)


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
        df = sf.load_markets().reset_index()
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
            payload = row.to_dict()
            payload["extracted_at"] = extracted_at
            return Market.model_validate(payload)
        except Exception as exc:
            logger.warning(f"Skipping market row {row.get('MarketId', 'Unknown')}: {exc}")
            return None
