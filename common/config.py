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


class _AnalystCleanupConfig:
    """Settings for analyst maintenance cleanup jobs."""

    def __init__(self, source: EnvYAML) -> None:
        retention_key = "analyst.cleanup.dataRetentionDays"
        self.data_cleanup_cron: str = source.get("analyst.cleanup.dataCleanupCron", "0 3 * * *")
        self.data_retention_days: int = self._positive_int(source.get(retention_key, 3), retention_key)

    @staticmethod
    def _positive_int(value: object, key: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a positive integer") from exc

        if parsed < 1:
            raise ValueError(f"{key} must be a positive integer")
        return parsed


class _KafkaTopicsConfig:
    """Canonical output topic names."""

    def __init__(self, source: EnvYAML) -> None:
        self.ticker: str = source.get("kafka.topics.ticker")
        self.income_statement: str = source.get("kafka.topics.incomeStatement")
        self.balance_sheet: str = source.get("kafka.topics.balanceSheet")
        self.cash_flow_statement: str = source.get("kafka.topics.cashFlowStatement")
        self.share_price_batch: str = source.get("kafka.topics.sharePriceBatch")
        self.analyst_request: str = source.get("kafka.topics.analystRequest")
        self.market: str = source.get("kafka.topics.market")
        self.industry: str = source.get("kafka.topics.industry")
        self.data_file_ready: str = source.get("kafka.topics.dataFileReady", "oraculum.data_file_ready")


class _LlmDeploymentConfig:
    """Settings for a specific LLM deployment."""

    def __init__(self, data: dict) -> None:
        self.alias: str = data.get("alias", "")
        self.model: str = data.get("model", "")
        self.api_key: str = data.get("api_key", "")
        self.api_base: str = data.get("api_base", "")
        self.order: int = data.get("order", 1)


class _LlmRouterSettingsConfig:
    """Global settings for the LLM router."""

    def __init__(self, data: dict) -> None:
        self.temperature: float = float(data.get("temperature", 0.0))
        self.num_retries: int = int(data.get("num_retries", 3))
        self.workflow_token_budget: int = int(data.get("workflow_token_budget", 100000))
        self.max_tokens: int = int(data.get("max_tokens", 16384))


class _LlmConfig:
    """Settings for the Large Language Model provider."""

    def __init__(self, source: EnvYAML) -> None:
        deployments_data = source.get("llm.deployments", [])
        self.deployments: List[_LlmDeploymentConfig] = [
            _LlmDeploymentConfig(d) for d in deployments_data
        ]
        self.router_settings: _LlmRouterSettingsConfig = _LlmRouterSettingsConfig(
            source.get("llm.router_settings", {})
        )

    @staticmethod
    def _positive_int(value: object, key: str) -> int:
        try:
            parsed = int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a positive integer") from exc

        if parsed < 1:
            raise ValueError(f"{key} must be a positive integer")
        return parsed

    @staticmethod
    def _positive_float(value: object, key: str) -> float:
        try:
            parsed = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{key} must be a positive float") from exc

        if parsed < 0.0:
            raise ValueError(f"{key} must be a positive float")
        return parsed


class Config:
    """Typed accessor over the YAML/env configuration file."""

    def __init__(self) -> None:
        source: EnvYAML = EnvYAML(
            yaml_file=str(CONFIG_PATH),
            env_file=str(ENV_PATH) if ENV_PATH.exists() else None,
        )
        self._source = source
        self.simfin_api_key: str = source.get("simfin.apiKey")
        self.simfin_chunk_size: int = self._positive_int(source.get("simfin.chunkSize", 500000), "simfin.chunkSize")
        self.simfin_refresh_days: int = self._positive_int(source.get("simfin.refreshDays", 1), "simfin.refreshDays")
        self.alpha_vantage_api_url: str = source.get("alphaVantage.apiUrl")
        self.alpha_vantage_api_key: str = source.get("alphaVantage.apiKey")
        self.kafka_brokers: List[str] = self._parse_brokers(source.get("kafka.brokers"))
        self.harvester_consumer_group: str = source.get("harvester.consumerGroup")
        self.harvester_request_topic: str = source.get("harvester.requestTopic")

        # Resolve data paths relative to the project root to avoid issues when
        # starting services from different working directories.
        raw_data_path = source.get("harvester.dataPath", "./data")
        self.harvester_data_path: Path = _ROOT_DIR / Path(raw_data_path)

        self.database_url: str = source.get("database.url")
        self.analyst_consumer_group: str = source.get("analyst.consumerGroup")
        self.analyst_refresh: _AnalystRefreshConfig = _AnalystRefreshConfig(source)
        self.analyst_cleanup: _AnalystCleanupConfig = _AnalystCleanupConfig(source)
        self.topics: _KafkaTopicsConfig = _KafkaTopicsConfig(source)
        self.llm: _LlmConfig = _LlmConfig(source)

        raw_shared_path = source.get("shared.folderPath", "./data/shared/simfin")
        self.shared_folder_path: Path = _ROOT_DIR / Path(raw_shared_path)
        self.shared_folder_path.mkdir(parents=True, exist_ok=True)

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
