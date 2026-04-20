"""Handler for `FetchStatementRequest` (skeleton)."""
from __future__ import annotations

from typing import Type

from common.requests import FetchStatementRequest, Request
from harvester.handlers.base import RequestHandler


class StatementRequestHandler(RequestHandler):
    """TODO: iterate SimFin income/balance/cashflow and publish statements."""

    @property
    def handles(self) -> Type[Request]:
        return FetchStatementRequest

    def handle(self, request: Request) -> None:
        raise NotImplementedError("FetchStatementRequest handler pending")
