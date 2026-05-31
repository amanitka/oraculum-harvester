"""Tests for request topic resolution in Kafka publisher."""

from __future__ import annotations

from common.messaging.kafka_publisher import KafkaRequestPublisher


def test_topic_map_routes_fetch_company_to_harvester_topic() -> None:
    """Route new company refresh requests through the harvester topic map."""
    publisher = KafkaRequestPublisher()

    assert publisher._topic_map["fetch_company"]
    assert "fetch_ticker" not in publisher._topic_map
