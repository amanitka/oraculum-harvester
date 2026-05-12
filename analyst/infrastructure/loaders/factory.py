"""Provides a factory to get the correct Parquet merge strategy for a dataset."""

from __future__ import annotations

from analyst.infrastructure.loaders.balance_sheet import BalanceSheetStrategy
from analyst.infrastructure.loaders.base import ParquetMergeStrategy
from analyst.infrastructure.loaders.cash_flow_statement import CashFlowStatementStrategy
from analyst.infrastructure.loaders.derived import DerivedStrategy
from analyst.infrastructure.loaders.income_statement import IncomeStatementStrategy
from analyst.infrastructure.loaders.share_price import SharePriceStrategy
from analyst.infrastructure.loaders.ticker import TickerStrategy

_STRATEGIES: dict[str, ParquetMergeStrategy] = {
    "ticker": TickerStrategy(),
    "share_price": SharePriceStrategy(),
    "balance_sheet": BalanceSheetStrategy(),
    "income_statement": IncomeStatementStrategy(),
    "cash_flow_statement": CashFlowStatementStrategy(),
    "derived": DerivedStrategy(),
}


def get_strategy(dataset: str) -> ParquetMergeStrategy | None:
    """
    Return the merge strategy instance for the given dataset.

    Args:
        dataset: The name of the dataset (e.g., 'ticker').

    Returns:
        An instance of a ParquetMergeStrategy, or None if not found.
    """
    return _STRATEGIES.get(dataset)
