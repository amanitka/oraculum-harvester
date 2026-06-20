"""Typed publishers for every harvester output topic.

Exposing them as module-level attributes keeps service code declarative
and gives FastStream the Pydantic schemas it needs for AsyncAPI docs
(`faststream docs gen harvester.app:app`).
"""

from __future__ import annotations

from common.config import config
from common.domain import (
    DataFileReadyEvent,
)
from harvester.app import broker

data_file_ready = broker.publisher(config.topics.data_file_ready, schema=DataFileReadyEvent)

