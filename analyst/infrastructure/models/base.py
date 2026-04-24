"""Shared building blocks for analyst SQLModel tables."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """Return the current UTC timestamp (module-level for test patchability)."""
    return datetime.now(timezone.utc)


class AuditMixin(SQLModel):
    """Audit columns shared by every analyst-owned table.

    `created_at` is set once on insert; `updated_at` is set on insert and
    must be refreshed by the repository on every update.
    """

    created_at: datetime = Field(default_factory=_utcnow)
    updated_at: datetime = Field(default_factory=_utcnow)
