"""Handler for `FetchTickerCommand`."""
from __future__ import annotations

import logging
from typing import Iterable, Type

from common import Ticker
from common.commands import Command, FetchTickerCommand
from common.config import config
from common.messaging import KafkaProducerProvider
from harvester.handlers.base import CommandHandler
from harvester.providers import ProviderRegistry, SupportsTickers

logger = logging.getLogger(__name__)


class TickerCommandHandler(CommandHandler):
    """Streams tickers from the requested provider onto the ticker topic."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers

    @property
    def handles(self) -> Type[Command]:
        return FetchTickerCommand

    def handle(self, command: Command) -> None:
        assert isinstance(command, FetchTickerCommand)  # noqa: S101
        provider = self._providers.get(command.provider, SupportsTickers)
        count = self._publish(provider.fetch_tickers(market=command.market))
        logger.info(
            "Published %d tickers [cid=%s provider=%s market=%s]",
            count,
            command.correlation_id,
            command.provider,
            command.market,
        )

    def _publish(self, tickers: Iterable[Ticker]) -> int:
        producer = KafkaProducerProvider.get()
        topic = config.topics.ticker
        count = 0
        for ticker in tickers:
            producer.send(
                topic,
                key=ticker.symbol,
                value=ticker.model_dump(by_alias=False, mode="json"),
            )
            count += 1
        producer.flush()
        return count
