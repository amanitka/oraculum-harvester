"""Harvester service entry point.

Consumes requests from `oraculum.harvester.request` and dispatches them
to typed handlers. One process handles commands sequentially; scale
horizontally by deploying more replicas in the same Kafka consumer
group (Kafka partitioning provides parallelism).
"""
from __future__ import annotations

import logging
from typing import Optional

import pandas as pd
from pydantic import ValidationError

from common.commands import Command, parse_command
from common.config import config
from common.messaging import KafkaConsumerProvider
from harvester.dispatcher import CommandDispatcher
from harvester.handlers import (
    RatioCommandHandler,
    StatementCommandHandler,
    TickerCommandHandler,
)
from harvester.providers import ProviderRegistry

logger = logging.getLogger(__name__)

_original_read_csv = pd.read_csv


def _patched_read_csv(*args, **kwargs):
    # Pandas 2.0+ removed `date_parser`; keep legacy SimFin calls working.
    kwargs.pop("date_parser", None)
    return _original_read_csv(*args, **kwargs)


pd.read_csv = _patched_read_csv


class HarvesterService:
    """Consumes harvester requests and dispatches them."""

    def __init__(
        self,
        dispatcher: CommandDispatcher,
        topic: Optional[str] = None,
    ) -> None:
        self._dispatcher = dispatcher
        self._topic = topic or config.harvester_request_topic

    def run(self) -> None:
        consumer = KafkaConsumerProvider.get(self._topic)
        logger.info("Listening on %s", self._topic)
        for message in consumer:
            self._process(message)
            consumer.commit()

    def _process(self, message) -> None:
        command = self._safe_parse(message)
        if command is None:
            return
        self._safe_dispatch(command)

    @staticmethod
    def _safe_parse(message) -> Optional[Command]:
        try:
            return parse_command(message.value)
        except ValidationError as exc:
            logger.error(
                "Invalid command at offset=%s: %s", message.offset, exc
            )
        except Exception:  # noqa: BLE001 - supervisor boundary
            logger.exception(
                "Unexpected parse error at offset=%s", message.offset
            )
        return None

    def _safe_dispatch(self, command: Command) -> None:
        try:
            self._dispatcher.dispatch(command)
        except Exception:  # noqa: BLE001 - supervisor boundary; log & commit
            logger.exception(
                "Handler failed for command_type=%s cid=%s",
                command.command_type,
                command.correlation_id,
            )


def build_default_service() -> HarvesterService:
    """Composition root: wire registry, handlers, dispatcher, and service."""
    providers = ProviderRegistry()
    dispatcher = CommandDispatcher(
        [
            TickerCommandHandler(providers),
            StatementCommandHandler(providers),
            RatioCommandHandler(providers),
        ]
    )
    return HarvesterService(dispatcher)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    build_default_service().run()


if __name__ == "__main__":
    main()
