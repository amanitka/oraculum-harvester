"""Base class for request handlers."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Type

from common.requests import Request


class RequestHandler(ABC):
    """Processes exactly one request type.

    The dispatcher keys handlers by the `handles` property, so each
    subclass must advertise the concrete request subclass it accepts.
    """

    @property
    @abstractmethod
    def handles(self) -> Type[Request]:
        """Concrete request subclass this handler accepts."""

    @abstractmethod
    def handle(self, request: Request) -> None:
        """Execute the work described by `request`."""
