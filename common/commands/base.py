"""Base class for every request published on `oraculum.harvester.request`."""
from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Command(BaseModel):
    """Common envelope fields shared by every harvester request.

    Concrete subclasses declare a literal `command_type` that acts as
    the discriminator in the tagged union (see `common.commands.AnyCommand`).
    """

    model_config = ConfigDict(extra="forbid")

    command_type: str
    correlation_id: UUID = Field(default_factory=uuid4)
    issued_at: datetime = Field(default_factory=_utcnow)
    provider: str
