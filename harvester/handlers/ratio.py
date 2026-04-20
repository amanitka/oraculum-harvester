"""Handler for `FetchRatioCommand` (skeleton)."""
from __future__ import annotations

from typing import Type

from common.commands import Command, FetchRatioCommand
from harvester.handlers.base import CommandHandler
from harvester.providers import ProviderRegistry


class RatioCommandHandler(CommandHandler):
    """TODO: iterate SimFin derived ratios and publish to ratio topic."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers

    @property
    def handles(self) -> Type[Command]:
        return FetchRatioCommand

    def handle(self, command: Command) -> None:
        raise NotImplementedError("FetchRatioCommand handler pending")
