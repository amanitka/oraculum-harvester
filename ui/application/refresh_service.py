"""Execute manual refresh actions triggered from the UI."""

from __future__ import annotations

from common.requests.base import Request
from application.ports import RefreshRequestPublisher


class RefreshService:
    """Coordinate refresh request dispatch from UI commands."""

    def __init__(self, publisher: RefreshRequestPublisher) -> None:
        self._publisher = publisher

    async def trigger(self, request: Request) -> None:
        """Trigger a refresh by publishing a request message."""
        await self._publisher.publish(request)
