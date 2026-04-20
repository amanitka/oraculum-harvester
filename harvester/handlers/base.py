"""Base class for command handlers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from common.commands import Command


class CommandHandler(ABC):
    """Processes exactly one command type.

    The dispatcher keys handlers by the `handles` property, so each
    subclass must advertise the concrete command subclass it accepts.
    """

    @property
    @abstractmethod
    def handles(self) -> Type[Command]:
        """Concrete command subclass this handler accepts."""

    @abstractmethod
    def handle(self, command: Command) -> None:
        """Execute the work described by `command`."""
