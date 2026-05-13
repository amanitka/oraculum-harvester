"""Tests for harvester request parsing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from common.requests import parse_request


def test_parse_request_rejects_fetch_derived() -> None:
    """Ensure derived metrics are no longer a harvester refresh request."""
    with pytest.raises(ValidationError):
        parse_request(
            {
                "request_type": "fetch_derived",
                "market": "us",
                "variant": "ttm",
                "templates": ["general"],
            }
        )
