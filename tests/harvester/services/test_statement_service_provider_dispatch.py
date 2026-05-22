"""Regression tests for statement service provider dispatch."""

from __future__ import annotations

import asyncio
from typing import Any, cast

import harvester
from common.requests.balance_sheet import FetchBalanceSheetRequest
from common.requests.cash_flow_statement import FetchCashFlowStatementRequest
from harvester.services import balance_sheet as balance_sheet_module
from harvester.services import cash_flow_statement as cash_flow_statement_module
from harvester.services.balance_sheet import BalanceSheetService
from harvester.services.cash_flow_statement import CashFlowStatementService


class _DataFileReadyPublisher:
    def __init__(self) -> None:
        self.events: list[tuple[Any, str | None]] = []

    async def publish(self, event: Any, key: str | None = None) -> None:
        self.events.append((event, key))


class _Publishers:
    def __init__(self) -> None:
        self.data_file_ready = _DataFileReadyPublisher()


class _BalanceSheetProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def fetch_balance_sheet(
        self,
        *,
        market: str,
        variant: str,
        template: str,
    ) -> list[object]:
        self.calls.append({"market": market, "variant": variant, "template": template})
        return [object()]


class _CashFlowStatementProvider:
    def __init__(self) -> None:
        self.calls: list[dict[str, str]] = []

    def fetch_cash_flow_statement(
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


def _install_service_fakes(monkeypatch: Any, service_module: Any) -> _DataFileReadyPublisher:
    publishers = _Publishers()
    monkeypatch.setattr(harvester, "publishers", publishers, raising=False)
    monkeypatch.setattr(service_module, "write_to_parquet", _write_to_parquet)
    return publishers.data_file_ready


def test_balance_sheet_service_dispatches_to_singular_provider_method(
    monkeypatch: Any,
) -> None:
    """Ensure balance sheet requests call the provider's singular fetch method."""
    publisher = _install_service_fakes(monkeypatch, balance_sheet_module)
    provider = _BalanceSheetProvider()
    request = FetchBalanceSheetRequest(market="us", variant="ttm", templates=["general"])

    service = BalanceSheetService(cast(Any, provider))
    asyncio.run(service.fetch_and_publish(request))

    assert provider.calls == [{"market": "us", "variant": "ttm", "template": "general"}]
    assert publisher.events[0][1] == f"balance_sheet:{request.correlation_id}"


def test_cash_flow_service_dispatches_to_singular_provider_method(
    monkeypatch: Any,
) -> None:
    """Ensure cash flow requests call the provider's singular fetch method."""
    publisher = _install_service_fakes(monkeypatch, cash_flow_statement_module)
    provider = _CashFlowStatementProvider()
    request = FetchCashFlowStatementRequest(market="us", variant="quarterly", templates=["banks"])

    service = CashFlowStatementService(cast(Any, provider))
    asyncio.run(service.fetch_and_publish(request))

    assert provider.calls == [{"market": "us", "variant": "quarterly", "template": "banks"}]
    assert publisher.events[0][1] == f"cash_flow_statement:{request.correlation_id}"
