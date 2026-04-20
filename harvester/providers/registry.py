"""Provider lookup by name with capability verification."""
from __future__ import annotations

from typing import Dict, Type, TypeVar

from harvester.providers.simfin import SimFinProvider

T = TypeVar("T")


class ProviderCapabilityError(Exception):
    """Raised when a provider does not implement the requested capability."""


class ProviderRegistry:
    """Resolves a provider instance by name and enforces capabilities."""

    def __init__(self) -> None:
        self._by_name: Dict[str, object] = {
            SimFinProvider.NAME: SimFinProvider(),
        }

    def names(self) -> list[str]:
        return list(self._by_name.keys())

    def get(self, name: str, capability: Type[T]) -> T:
        """Return the named provider if it implements the given capability."""
        provider = self._by_name.get(name)
        if provider is None:
            raise KeyError(f"Unknown provider: {name!r}")
        if not isinstance(provider, capability):
            raise ProviderCapabilityError(
                f"Provider {name!r} does not implement "
                f"{capability.__name__}"
            )
        return provider  # type: ignore[return-value]
