"""Regression tests for company service parquet publishing."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import harvester
from common.requests.company import FetchCompanyRequest
from harvester.services import company as company_service_module
from harvester.services.company import CompanyService


class _DataFileReadyPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[Any, str | None]] = []

    async def publish(self, event: Any, key: str | None = None) -> None:
        self.events.append((event, key))


class _Publishers:
    def __init__(self) -> None:
        self.data_file_ready = _DataFileReadyPublisher()


class _CompanyProvider:
    def __init__(self) -> None:
        self.markets: list[str] = []

    def fetch_companies(self, *, market: str) -> list[object]:
        self.markets.append(market)
        return [object()]


def _write_to_parquet(*, models: list[object], dataset: str, run_id: str) -> dict[str, Any]:
    return {
        "checksum": "sha256",
        "count": len(models),
        "path": f"{dataset}/{run_id}",
    }


def test_company_service_writes_company_dataset_and_publishes_event(monkeypatch: Any) -> None:
    """Publish a company data-file-ready event after writing parquet."""
    publishers = _Publishers()
    monkeypatch.setattr(harvester, "publishers", publishers, raising=False)
    monkeypatch.setattr(company_service_module, "write_to_parquet", _write_to_parquet)

    provider = _CompanyProvider()
    request = FetchCompanyRequest(market="us")

    service = CompanyService(cast(Any, provider))
    asyncio.run(service.fetch_and_publish(request))

    assert provider.markets == ["us"]
    event, key = publishers.data_file_ready.events[0]
    assert event.dataset == "company"
    assert key == f"company:{request.correlation_id}"
