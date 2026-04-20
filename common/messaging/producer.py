"""Process-wide Kafka/Redpanda producer provider.

`KafkaProducer` is already thread-safe and designed to be shared across
threads in a single process. We wrap it in a lazy, thread-safe provider
so that:

* the connection is not opened at import time,
* the lifecycle (flush + close) is explicit and hooked into `atexit`,
* tests can call `reset()` to swap or drop the instance.
"""
from __future__ import annotations

import atexit
import json
import threading
from datetime import date, datetime
from typing import Any, Optional

from kafka import KafkaProducer

from common.config import config


def _json_default(obj: Any) -> Any:
    """Fallback encoder for non-standard JSON types (datetime, Decimal...)."""
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"{type(obj).__name__} is not JSON serializable")


def _serialize_value(value: Any) -> bytes:
    return json.dumps(value, default=_json_default).encode("utf-8")


def _serialize_key(key: Any) -> Optional[bytes]:
    if key is None:
        return None
    return key.encode("utf-8") if isinstance(key, str) else bytes(key)


class KafkaProducerProvider:
    """Lazy, thread-safe singleton wrapper around `KafkaProducer`."""

    _instance: Optional[KafkaProducer] = None
    _lock: threading.Lock = threading.Lock()
    _atexit_registered: bool = False

    @classmethod
    def get(cls) -> KafkaProducer:
        """Return the shared producer, creating it on first access."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._build()
                    cls._register_shutdown_hook()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Close and drop the shared instance (primarily for tests)."""
        with cls._lock:
            if cls._instance is not None:
                cls._safe_close(cls._instance)
                cls._instance = None

    @staticmethod
    def _build() -> KafkaProducer:
        return KafkaProducer(
            bootstrap_servers=config.redpanda_brokers,
            value_serializer=_serialize_value,
            key_serializer=_serialize_key,
            acks="all",
            linger_ms=20,
        )

    @classmethod
    def _register_shutdown_hook(cls) -> None:
        if cls._atexit_registered:
            return
        atexit.register(cls.reset)
        cls._atexit_registered = True

    @staticmethod
    def _safe_close(producer: KafkaProducer) -> None:
        try:
            producer.flush()
        finally:
            producer.close()
