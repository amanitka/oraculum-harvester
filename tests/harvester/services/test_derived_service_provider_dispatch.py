"""Regression tests for derived service provider dispatch."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import harvester
from common.requests.derived import FetchDerivedRequest
from harvester.services import derived as derived_module
from harvester.services.derived import DerivedService


class _DataFileReadyPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[Any, str | None]] = []

    async def publish(self, event: Any, key: str | None = None) -> None:
        self.events.append((event, key))


class _Publishers:
    def __init__(self) -> None:
        self.data_file_ready = _DataFileReadyPublisher()


class _DerivedProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def fetch_derived(
        self,
        *,
        market: str,
        variant: str,
        template: str,
    ) -> list[object]:
        self.calls.append({"market": market, "variant": variant, "template": template})
        return [object()]


def _write_to_parquet(
    *,
    models: list[object],
    dataset: str,
    run_id: str,
    template: str,
    variant: str,
) -> dict[str, Any]:
    return {"checksum": "sha256", "count": len(models), "path": f"{dataset}/{run_id}"}


def test_derived_service_dispatches_to_provider_method(monkeypatch: Any) -> None:
    """Ensure derived requests call the provider's derived fetch method."""
    publishers = _Publishers()
    monkeypatch.setattr(harvester, "publishers", publishers, raising=False)
    monkeypatch.setattr(derived_module, "write_to_parquet", _write_to_parquet)
    provider = _DerivedProvider()
    request = FetchDerivedRequest(market="us", variant="ttm", templates=["general"])

    service = DerivedService(cast(Any, provider))
    asyncio.run(service.fetch_and_publish(request))

    assert provider.calls == [{"market": "us", "variant": "ttm", "template": "general"}]
    assert publishers.data_file_ready.events[0][0].dataset == "derived"
    assert publishers.data_file_ready.events[0][1] == f"derived:{request.correlation_id}"
