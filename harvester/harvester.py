import json
import math
from pathlib import Path

import pandas as pd
from kafka import KafkaProducer

from common import Ticker
from common.config import config
import simfin as sf

original_read_csv = pd.read_csv


def patched_read_csv(*args, **kwargs):
    if 'date_parser' in kwargs:
        # In Pandas 2.0+, date_parser is replaced by date_format or ignored
        # because the new parser is much smarter.
        kwargs.pop('date_parser')
    return original_read_csv(*args, **kwargs)


pd.read_csv = patched_read_csv


class TickerHarvester:
    def __init__(self):
        # Initialize SimFin
        sf.set_api_key(config.simfin_api_key)
        cache_path = Path("./data/simfin_cache")
        cache_path.mkdir(parents=True, exist_ok=True)
        sf.set_data_dir(str(cache_path))

        # Initialize Producer (Sync for Harvester)
        self.producer = KafkaProducer(
            bootstrap_servers=config.redpanda_brokers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.topic = config.ticker_topic

    @staticmethod
    def get_industry_map():
        """Fetches industry names to enrich the ticker data."""
        print("Loading industry metadata...")
        df_ind = sf.load_industries()
        return df_ind.to_dict(orient='index')

    def run(self):
        # 1. Prepare Enrichment Data
        industry_map = self.get_industry_map()

        # 2. Fetch US Companies
        print("Fetching US tickers from SimFin...")
        df = sf.load_companies(market='us').reset_index()

        # 3. Process each row
        success = 0
        for _, row in df.iterrows():
            try:
                # 1. Start with the raw SimFin dictionary
                raw_simfin_dict = row.to_dict()

                # 2. Add the provider name manually
                raw_simfin_dict['provider_name'] = 'simfin'

                # 3. Handle Enrichment (still using SimFin names for logic)
                raw_id = raw_simfin_dict.get("IndustryId")
                if raw_id is not None and not (isinstance(raw_id, float) and math.isnan(raw_id)):
                    idx = int(float(raw_id))
                    if idx in industry_map:
                        # We map these to our INTERNAL names directly
                        raw_simfin_dict['industry_name'] = industry_map[idx].get('Industry')
                        raw_simfin_dict['sector_name'] = industry_map[idx].get('Sector')

                # 4. VALIDATE: This consumes SimFin names (via Aliases)
                ticker_obj = Ticker.model_validate(raw_simfin_dict)

                # 5. CONVERT: This is the magic part!
                # by_alias=False tells Pydantic to use your Python field names (symbol, company_name)
                # instead of the aliases (Ticker, Company Name).
                standardized_dict = ticker_obj.model_dump(by_alias=False)

                # 6. Publish the standardized version to Redpanda
                self.producer.send(
                    self.topic,
                    key=ticker_obj.symbol.encode('utf-8'),
                    value=standardized_dict
                )
                success += 1

            except Exception as e:
                print(f"Error translating {row.get('Ticker', 'Unknown')}: {e}")

        self.producer.flush()
        print(f"Success: Published {success} standardized tickers.")


if __name__ == "__main__":
    harvester = TickerHarvester()
    harvester.run()