"""Tests for harvester request parsing."""

from __future__ import annotations

from common.requests import FetchDerivedRequest, parse_request


def test_parse_request_accepts_fetch_derived() -> None:
    """Ensure the request union recognizes derived refresh requests."""
    request = parse_request(
        {
            "request_type": "fetch_derived",
            "market": "us",
            "variant": "ttm",
            "templates": ["general"],
        }
    )

    assert isinstance(request, FetchDerivedRequest)
    assert request.market == "us"
    assert request.variant == "ttm"
    assert request.templates == ["general"]
