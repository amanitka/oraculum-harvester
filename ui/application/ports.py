"""Define application-layer ports for UI refresh commands."""

from __future__ import annotations

from abc import ABC, abstractmethod

from common.requests.base import Request


class RefreshRequestPublisher(ABC):
    """Publish refresh requests to a transport channel."""

    @abstractmethod
    async def publish(self, request: Request) -> None:
        """Publish one refresh request message."""
