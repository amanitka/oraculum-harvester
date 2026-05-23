import json
import logging
from typing import Optional

import requests

from common.config import config

logger = logging.getLogger(__name__)


class AlphaVantageProvider:
    def __init__(self):
        self.api_key = config.alpha_vantage_api_key
        self.base_url = f"{config.alpha_vantage_api_url}/query"

    def fetch_news_sentiment(self, time_from: Optional[str] = None, time_to: Optional[str] = None) -> json:
        params = {"function": "NEWS_SENTIMENT", "apikey": self.api_key, "limit": 1000}
        if time_from:
            params["time_from"] = time_from
        if time_to:
            params["time_to"] = time_to

        try:
            response = requests.get(self.base_url, params=params)
            response.raise_for_status()
            data = response.json()

            # Check for "Information" or "Error" keys returned by Alpha Vantage
            if "Information" in data:
                logger.warning(f"Alpha Vantage API rate limit or info: {data['Information']}")
            return data

        except requests.exceptions.RequestException as e:
            logger.error(f"Network error: {e}")
            return {}
