"""Typed facade over the YAML/env configuration file."""
from __future__ import annotations

from pathlib import Path
from typing import List

from envyaml import EnvYAML

_CURRENT_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _CURRENT_DIR.parent
CONFIG_PATH = _ROOT_DIR / "config.yaml"


class _KafkaTopicsConfig:
    """Canonical output topic names."""

    def __init__(self, source: EnvYAML) -> None:
        self.ticker: str = source.get("kafka.topics.ticker")
        self.income_statement: str = source.get("kafka.topics.incomeStatement")
        self.balance_sheet: str = source.get("kafka.topics.balanceSheet")
        self.cash_flow_statement: str = source.get("kafka.topics.cashFlowStatement")


class Config:
    """Typed accessor over the YAML/env configuration file."""

    def __init__(self) -> None:
        source: EnvYAML = EnvYAML(CONFIG_PATH)
        self._source = source
        self.simfin_api_key: str = source.get("simFin.apiKey")
        self.kafka_brokers: List[str] = self._parse_brokers(
            source.get("kafka.brokers")
        )
        self.harvester_consumer_group: str = source.get("harvester.consumerGroup")
        self.harvester_request_topic: str = source.get("harvester.requestTopic")
        self.topics: _KafkaTopicsConfig = _KafkaTopicsConfig(source)

    @staticmethod
    def _parse_brokers(value: str | list | None) -> List[str]:
        if not value:
            return ["localhost:9092"]
        if isinstance(value, list):
            return value
        return [host.strip() for host in str(value).split(",") if host.strip()]


config: Config = Config()
