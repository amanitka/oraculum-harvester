"""Provider capability protocols.

Each protocol describes a slice of functionality a vendor may support.
Concrete providers (e.g. `SimFinProvider`) implement one or more of
these via duck typing; the `ProviderRegistry` uses `isinstance` checks
at runtime to verify required capabilities per command.
"""
from __future__ import annotations

from typing import Iterator, Protocol, runtime_checkable

from common import Ticker


@runtime_checkable
class Provider(Protocol):
    """Marker contract every provider must satisfy."""

    @property
    def name(self) -> str: ...


@runtime_checkable
class SupportsTickers(Provider, Protocol):
    """Provider capable of fetching ticker master data."""

    def fetch_tickers(self, market: str = "us") -> Iterator[Ticker]: ...


# TODO: SupportsStatements, SupportsRatios once those handlers are built.
