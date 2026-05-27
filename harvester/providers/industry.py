"""SimFin industry data provider."""

import logging
from datetime import datetime, timezone
from typing import Iterator

import pandas as pd
import simfin as sf

from common.config import config
from common.domain.industry import Industry

logger = logging.getLogger(__name__)

SIMFIN_INDUSTRY_ID_KEY = "IndustryId"
SIMFIN_SECTOR_KEY = "Sector"
SIMFIN_INDUSTRY_NAME_KEY = "Industry"
INDUSTRY_BANK_KEYWORD = "bank"
INDUSTRY_INSURANCE_KEYWORD = "insurance"


class IndustryProvider:
    """Fetches industry metadata from SimFin."""

    def __init__(self) -> None:
        cache_path = config.harvester_data_path / "simfin_cache"
        sf.set_api_key(config.simfin_api_key)
        cache_path.mkdir(parents=True, exist_ok=True)
        sf.set_data_dir(str(cache_path))

    def fetch_industries(self) -> Iterator[Industry]:
        """Yield validated `Industry` records."""
        logger.info("Loading industries from SimFin")
        # Added refresh_days parameter from config
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

        logger.info(f"Industry load summary: published={published} skipped={skipped}")

    @staticmethod
    def _data_row_to_industry(row: pd.Series, extracted_at: datetime) -> Industry | None:
        try:
            source_payload = row.to_dict()
            industry_name = source_payload.get(SIMFIN_INDUSTRY_NAME_KEY)
            payload = {
                "industryId": source_payload.get(SIMFIN_INDUSTRY_ID_KEY),
                "sectorName": source_payload.get(SIMFIN_SECTOR_KEY),
                "industryName": industry_name,
                "statementTemplate": IndustryProvider._map_statement_template(industry_name),
                "extractedAt": extracted_at,
            }
            return Industry.model_validate(payload)
        except Exception as exc:
            logger.warning(f"Skipping industry row {row.get(SIMFIN_INDUSTRY_ID_KEY, 'Unknown')}: {exc}")
            return None

    @staticmethod
    def _map_statement_template(industry_name: str | None) -> str:
        """Map SimFin industry names to internal statement templates."""
        if not industry_name:
            return "general"
        normalized_name = industry_name.lower()
        if INDUSTRY_BANK_KEYWORD in normalized_name:
            return "banks"
        if INDUSTRY_INSURANCE_KEYWORD in normalized_name:
            return "insurance"
        return "general"
