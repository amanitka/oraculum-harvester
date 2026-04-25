"""Typed publishers for every harvester output topic.

Exposing them as module-level attributes keeps service code declarative
and gives FastStream the Pydantic schemas it needs for AsyncAPI docs
(`faststream docs gen harvester.app:app`).
"""

from __future__ import annotations

from common.config import config
from common.domain import (
    BalanceSheet,
    CashFlowStatement,
    IncomeStatement,
    Ticker,
)
from harvester.app import broker

ticker = broker.publisher(config.topics.ticker, schema=Ticker)
income_statement = broker.publisher(
    config.topics.income_statement, schema=IncomeStatement
)
balance_sheet = broker.publisher(
    config.topics.balance_sheet, schema=BalanceSheet
)
cash_flow_statement = broker.publisher(
    config.topics.cash_flow_statement, schema=CashFlowStatement
)
