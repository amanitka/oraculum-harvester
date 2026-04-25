"""Process-wide async SQLAlchemy engine provider.

A single `AsyncEngine` per process, lazily constructed, with explicit
shutdown via `dispose()`. Tests call `dispose()` to swap in an
alternative engine (e.g. SQLite in-memory) or drop the shared instance.

`psycopg[binary]` 3.x is unified sync/async on the same URL scheme, so
Alembic's sync migrations and the analyst's async runtime share the
same `config.database_url`.
"""

from __future__ import annotations

import asyncio
from typing import Optional

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    async_sessionmaker,
    create_async_engine,
)
from sqlmodel.ext.asyncio.session import AsyncSession

from common.config import config


class EngineProvider:
    """Lazy, async-safe singleton wrapper around an `AsyncEngine`."""

    _engine: Optional[AsyncEngine] = None
    _sessionmaker: Optional[async_sessionmaker[AsyncSession]] = None
    _lock: asyncio.Lock = asyncio.Lock()

    @classmethod
    async def session_factory(cls) -> async_sessionmaker[AsyncSession]:
        """Return the shared session factory, building it on first call."""
        if cls._sessionmaker is None:
            async with cls._lock:
                if cls._sessionmaker is None:
                    cls._engine = create_async_engine(
                        config.database_url, echo=False
                    )
                    cls._sessionmaker = async_sessionmaker(
                        cls._engine,
                        class_=AsyncSession,
                        expire_on_commit=False,
                    )
        return cls._sessionmaker

    @classmethod
    async def dispose(cls) -> None:
        """Dispose of the engine and drop the shared instance."""
        engine = cls._engine
        cls._engine = None
        cls._sessionmaker = None
        if engine is not None:
            try:
                await engine.dispose()
            except Exception:  # noqa: BLE001 - shutdown path; never raise
                pass
