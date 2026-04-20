"""Handler for `FetchRatioRequest` (skeleton)."""
from __future__ import annotations

from typing import Type

from common.requests import FetchRatioRequest, Request
from harvester.handlers.base import RequestHandler


class RatioRequestHandler(RequestHandler):
    """TODO: iterate SimFin derived ratios and publish to ratio topic."""

    @property
    def handles(self) -> Type[Request]:
        return FetchRatioRequest

    def handle(self, request: Request) -> None:
        raise NotImplementedError("FetchRatioRequest handler pending")
