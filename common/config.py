"""Typed facade over the YAML/env configuration file."""

from __future__ import annotations

from pathlib import Path
from typing import List

from envyaml import EnvYAML

_CURRENT_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _CURRENT_DIR.parent
CONFIG_PATH = _ROOT_DIR / "config.yaml"
ENV_PATH = _ROOT_DIR / ".env"


class _AnalystRefreshConfig:
    """Cron expressions for the analyst periodic refresh jobs."""

    def __init__(self, source: EnvYAML) -> None:
        self.price_cron: str = source.get("analyst.refresh.priceCron", "0 7 * * *")
        self.fundamentals_cron: str = source.get("analyst.refresh.fundamentalsCron", "0 0 * * 0")
        self.ticker_cron: str = source.get("analyst.refresh.tickerCron", "0 0 1 * *")


class _KafkaTopicsConfig:
    """Canonical output topic names."""

    def __init__(self, source: EnvYAML) -> None:
        self.ticker: str = source.get("kafka.topics.ticker")
        self.income_statement: str = source.get("kafka.topics.incomeStatement")
        self.balance_sheet: str = source.get("kafka.topics.balanceSheet")
        self.cash_flow_statement: str = source.get("kafka.topics.cashFlowStatement")
        self.share_price_batch: str = source.get("kafka.topics.sharePriceBatch")
        self.ratio: str = source.get("kafka.topics.ratio")


class Config:
    """Typed accessor over the YAML/env configuration file."""

    def __init__(self) -> None:
        source: EnvYAML = EnvYAML(
            yaml_file=str(CONFIG_PATH),
            env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        )
        self._source = source
        self.simfin_api_key: str = source.get("simfin.apiKey")
        self.kafka_brokers: List[str] = self._parse_brokers(source.get("kafka.brokers"))
        self.harvester_consumer_group: str = source.get("harvester.consumerGroup")
        self.harvester_request_topic: str = source.get("harvester.requestTopic")
        self.harvester_data_path: Path = Path(source.get("harvester.dataPath"))
        self.database_url: str = source.get("database.url")
        self.analyst_consumer_group: str = source.get("analyst.consumerGroup")
        self.analyst_refresh: _AnalystRefreshConfig = _AnalystRefreshConfig(source)
        self.topics: _KafkaTopicsConfig = _KafkaTopicsConfig(source)

    @staticmethod
    def _parse_brokers(value: str | list[str] | None) -> List[str]:
        if not value:
            return ["localhost:9092"]
        if isinstance(value, list):
            return value
        return [host.strip() for host in str(value).split(",") if host.strip()]


config: Config = Config()
