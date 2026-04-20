"""Routes requests to their registered handlers."""
from __future__ import annotations

from typing import Dict, Iterable, Type

from common.requests import Request
from harvester.handlers.base import RequestHandler


class UnknownRequestError(Exception):
    """Raised when no handler is registered for a request's type."""


class RequestDispatcher:
    """Holds the handler registry and routes requests by their runtime type."""

    def __init__(self, handlers: Iterable[RequestHandler]) -> None:
        self._by_type: Dict[Type[Request], RequestHandler] = {}
        for handler in handlers:
            self._register(handler)

    def dispatch(self, request: Request) -> None:
        handler = self._by_type.get(type(request))
        if handler is None:
            raise UnknownRequestError(
                f"No handler for request type: {type(request).__name__}"
            )
        handler.handle(request)

    def _register(self, handler: RequestHandler) -> None:
        key = handler.handles
        if key in self._by_type:
            raise ValueError(f"Duplicate handler for {key.__name__}")
        self._by_type[key] = handler
