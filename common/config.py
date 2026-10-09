"""Typed facade over the YAML/env configuration file."""

from __future__ import annotations

from pathlib import Path
from typing import Any, List

from envyaml import EnvYAML

_CURRENT_DIR = Path(__file__).resolve().parent
_ROOT_DIR = _CURRENT_DIR.parent
CONFIG_PATH = _ROOT_DIR / "config.yaml"
ENV_PATH = _ROOT_DIR / ".env"


class _KafkaTopicsConfig:
    """Canonical output topic names."""

    def __init__(self, source: EnvYAML) -> None:
        self.market: str = source.get("kafka.topics.market")
        self.industry: str = source.get("kafka.topics.industry")
        self.data_file_ready: str = source.get("kafka.topics.dataFileReady")


class Config:
    """Typed accessor over the YAML/env configuration file."""

    def __init__(self) -> None:
        source: EnvYAML = EnvYAML(
            yaml_file=str(CONFIG_PATH),
            env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        )
        self._source = source
        self.harvester_default_chunk_size: int = self._positive_int(
            source.get("harvester.defaultChunkSize", 1000000), "harvester.defaultChunkSize"
        )
        self.simfin_api_key: str = source.get("simfin.apiKey")
        self.simfin_chunk_size: int = self._positive_int(
            source.get("simfin.chunkSize", self.harvester_default_chunk_size), "simfin.chunkSize"
        )
        self.simfin_refresh_days: int = self._positive_int(source.get("simfin.refreshDays", 1), "simfin.refreshDays")
        self.kafka_brokers: List[str] = self._parse_brokers(source.get("kafka.brokers"))
        self.harvester_consumer_group: str = source.get("harvester.consumerGroup")
        self.harvester_request_topic: str = source.get("harvester.requestTopic")

        self.openinsider_base_url: str = source.get("openinsider.baseUrl", "http://openinsider.com/screener")
        self.openinsider_records_per_page: int = self._positive_int(source.get("openinsider.recordsPerPage", 1000), "openinsider.recordsPerPage")
        self.openinsider_delay_seconds: int = self._positive_int(source.get("openinsider.delaySeconds", 2), "openinsider.delaySeconds")
        self.openinsider_default_params: dict[str, Any] = source.get("openinsider.defaultParams", {})

        # Resolve data paths (handles absolute paths for Docker and relative paths for dev).
        raw_data_path = source.get("harvester.dataDirectory")
        parsed_data_path = Path(raw_data_path)
        self.harvester_data_directory: Path = parsed_data_path if parsed_data_path.is_absolute() else _ROOT_DIR / parsed_data_path
        self.topics: _KafkaTopicsConfig = _KafkaTopicsConfig(source)

        raw_exchange_path = source.get("harvester.exchangeDirectory")
        parsed_exchange_path = Path(raw_exchange_path)
        self.harvester_exchange_directory: Path = parsed_exchange_path if parsed_exchange_path.is_absolute() else _ROOT_DIR / parsed_exchange_path
        self.harvester_exchange_directory.mkdir(parents=True, exist_ok=True)

        self.harvester_temp_cleanup_enabled: bool = bool(source.get("harvester.tempCleanup.enabled", True))
        self.harvester_temp_cleanup_retention_days: int = self._positive_int(
            source.get("harvester.tempCleanup.retentionDays", 1), "harvester.tempCleanup.retentionDays"
        )
        self.harvester_temp_cleanup_interval_days: int = self._positive_int(
            source.get("harvester.tempCleanup.intervalDays", 1), "harvester.tempCleanup.intervalDays"
        )

        self.sec_user_agent: str = source.get(
            "sec.userAgent", "OraculumHarvester admin@oraculum-analytics.com"
        )
        self.sec_bulk_13f_base_urls: list[str] = self._parse_string_list(
            source.get("sec.bulk13fBaseUrls") or source.get("sec.bulk13fBaseUrl")
        )
        self.sec_bulk_13f_base_url: str = self.sec_bulk_13f_base_urls[0] if self.sec_bulk_13f_base_urls else ""

    @staticmethod
    def _parse_string_list(value: object) -> list[str]:
        if not value:
            return []
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return []

    @staticmethod
    def _parse_brokers(value: str | list[str] | None) -> List[str]:
        if not value:
            return ["localhost:9092"]
        if isinstance(value, list):
            return value
        return [host.strip() for host in str(value).split(",") if host.strip()]

    @staticmethod
    def _positive_int(value: object, key: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a positive integer") from exc

        if parsed < 0:
            raise ValueError(f"{key} must be a positive integer")
        return parsed


config: Config = Config()
