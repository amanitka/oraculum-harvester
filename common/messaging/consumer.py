"""Process-wide Kafka/Redpanda consumer provider.

Rationale mirrors `producer.py`: a single consumer per process, lazily
constructed, with explicit lifecycle via `reset()` and `atexit`. Tests
call `reset()` to swap topics or drop the shared instance.
"""
from __future__ import annotations

import atexit
import threading
from typing import Optional, Tuple

from kafka import KafkaConsumer

from common.config import config


class KafkaConsumerProvider:
    """Lazy, thread-safe singleton wrapper around `KafkaConsumer`."""

    _instance: Optional[KafkaConsumer] = None
    _topics: Tuple[str, ...] = ()
    _group_id: Optional[str] = None
    _lock: threading.Lock = threading.Lock()
    _atexit_registered: bool = False

    @classmethod
    def get(cls, *topics: str, group_id: Optional[str] = None) -> KafkaConsumer | None:
        """Return the shared consumer, building it on first call.

        Topics and group_id are read on creation; subsequent calls ignore
        them. Call `reset()` first if different subscriptions are needed.
        """
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls._build(
                        topics, group_id or config.harvester_consumer_group
                    )
                    cls._topics = topics
                    cls._group_id = group_id
                    cls._register_shutdown_hook()
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Close and drop the shared instance (primarily for tests)."""
        with cls._lock:
            if cls._instance is not None:
                cls._safe_close(cls._instance)
                cls._instance = None
                cls._topics = ()
                cls._group_id = None

    @staticmethod
    def _build(topics: Tuple[str, ...], group_id: str) -> KafkaConsumer:
        """

        :rtype: KafkaConsumer
        """
        return KafkaConsumer(
            *topics,
            bootstrap_servers=config.kafka_brokers,
            group_id=group_id,
            enable_auto_commit=False,
            auto_offset_reset="earliest",
            value_deserializer=lambda value: value,
        )

    @classmethod
    def _register_shutdown_hook(cls) -> None:
        if cls._atexit_registered:
            return
        atexit.register(cls.reset)
        cls._atexit_registered = True

    @staticmethod
    def _safe_close(consumer: KafkaConsumer) -> None:
        try:
            consumer.close()
        except Exception:  # noqa: BLE001 - shutdown path; never raise
            pass
