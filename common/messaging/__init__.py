"""Shared Kafka / FastStream infrastructure."""

from common.messaging.broker import create_broker

__all__ = ["create_broker"]
