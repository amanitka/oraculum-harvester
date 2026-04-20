"""Handler for `FetchStatementCommand` (skeleton)."""
from __future__ import annotations

from typing import Type

from common.commands import Command, FetchStatementCommand
from harvester.handlers.base import CommandHandler
from harvester.providers import ProviderRegistry


class StatementCommandHandler(CommandHandler):
    """TODO: iterate SimFin income/balance/cashflow and publish statements."""

    def __init__(self, providers: ProviderRegistry) -> None:
        self._providers = providers

    @property
    def handles(self) -> Type[Command]:
        return FetchStatementCommand

    def handle(self, command: Command) -> None:
        raise NotImplementedError("FetchStatementCommand handler pending")
