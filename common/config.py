"""Typed facade over the YAML/env configuration file."""
from __future__ import annotations

from pathlib import Path
from typing import List

from envyaml import EnvYAML

_CURRENT_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _CURRENT_DIR.parent
CONFIG_PATH = _ROOT_DIR / "config.yaml"


class _TopicsConfig:
    """Canonical output topic names."""

    def __init__(self, source: EnvYAML) -> None:
        self.ticker: str = source.get("topics.ticker")
        self.statement: str = source.get("topics.statement")
        self.ratio: str = source.get("topics.ratio")


class Config:
    """Typed accessor over the YAML/env configuration file."""

    def __init__(self) -> None:
        source: EnvYAML = EnvYAML(CONFIG_PATH)
        self._source = source
        self.simfin_api_key: str = source.get("simFin.apiKey")
        self.redpanda_brokers: List[str] = self._parse_brokers(
            source.get("redpanda.brokers")
        )
        self.harvester_consumer_group: str = source.get("harvester.consumerGroup")
        self.harvester_request_topic: str = source.get("harvester.requestTopic")
        self.topics: _TopicsConfig = _TopicsConfig(source)

    @staticmethod
    def _parse_brokers(value: str | list | None) -> List[str]:
        if not value:
            return ["localhost:9092"]
        if isinstance(value, list):
            return value
        return [host.strip() for host in str(value).split(",") if host.strip()]


config: Config = Config()
