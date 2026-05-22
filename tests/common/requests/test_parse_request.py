"""Tests for harvester request parsing."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from pydantic import TypeAdapter
from common.requests import AnyRequest

parse_request = TypeAdapter(AnyRequest).validate_python


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
