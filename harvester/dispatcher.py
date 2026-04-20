"""Routes commands to their registered handlers."""
from __future__ import annotations

from typing import Dict, Iterable, Type

from common.commands import Command
from harvester.handlers.base import CommandHandler


class UnknownCommandError(Exception):
    """Raised when no handler is registered for a command's type."""


class CommandDispatcher:
    """Holds the handler registry and routes commands by their runtime type."""

    def __init__(self, handlers: Iterable[CommandHandler]) -> None:
        self._by_type: Dict[Type[Command], CommandHandler] = {}
        for handler in handlers:
            self._register(handler)

    def dispatch(self, command: Command) -> None:
        handler = self._by_type.get(type(command))
        if handler is None:
            raise UnknownCommandError(
                f"No handler for command type: {type(command).__name__}"
            )
        handler.handle(command)

    def _register(self, handler: CommandHandler) -> None:
        key = handler.handles
        if key in self._by_type:
            raise ValueError(f"Duplicate handler for {key.__name__}")
        self._by_type[key] = handler
