"""Reusable FastStream dependencies for the analyst service."""

from __future__ import annotations

from typing import AsyncIterator

from faststream import Depends
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.engine import EngineProvider


async def _session_scope() -> AsyncIterator[AsyncSession]:
    """Yield a scoped `AsyncSession`; closes on subscriber return."""
    factory = await EngineProvider.session_factory()
    async with factory() as session:
        yield session


def Session() -> AsyncSession:  # noqa: N802 - declarative factory name
    """Inject a fresh `AsyncSession` into a FastStream subscriber."""
    return Depends(_session_scope)
