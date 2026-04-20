"""Discriminated union of all harvester request commands + a parser."""
from __future__ import annotations

from typing import Annotated, Union

from pydantic import Field, TypeAdapter, ValidationError

from common.commands.base import Command
from common.commands.ratio import FetchRatioCommand
from common.commands.statement import FetchStatementCommand
from common.commands.ticker import FetchTickerCommand

AnyCommand = Annotated[
    Union[FetchTickerCommand, FetchStatementCommand, FetchRatioCommand],
    Field(discriminator="command_type"),
]

_ADAPTER: TypeAdapter[AnyCommand] = TypeAdapter(AnyCommand)


def parse_command(payload: bytes | str | dict) -> Command:
    """Validate an incoming payload against the discriminated union.

    Raises `pydantic.ValidationError` on bad shapes so callers can treat
    invalid payloads as poison and route them to logs/DLQ.
    """
    if isinstance(payload, (bytes, str)):
        return _ADAPTER.validate_json(payload)
    return _ADAPTER.validate_python(payload)


__all__ = [
    "AnyCommand",
    "Command",
    "FetchRatioCommand",
    "FetchStatementCommand",
    "FetchTickerCommand",
    "ValidationError",
    "parse_command",
]
