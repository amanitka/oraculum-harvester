"""Per-aggregate persistence gateways for the analyst service."""

from analyst.infrastructure.repositories.balance_sheet import BalanceSheetRepository
from analyst.infrastructure.repositories.cash_flow_statement import (
    CashFlowStatementRepository,
)
from analyst.infrastructure.repositories.daily_market_signals import (
    DailyMarketSignalsRepository,
)
from analyst.infrastructure.repositories.derived_metrics import DerivedMetricsRepository
from analyst.infrastructure.repositories.income_statement import (
    IncomeStatementRepository,
)
from analyst.infrastructure.repositories.share_price import SharePriceRepository
from analyst.infrastructure.repositories.ticker import TickerRepository

__all__ = [
    "BalanceSheetRepository",
    "CashFlowStatementRepository",
    "DailyMarketSignalsRepository",
    "DerivedMetricsRepository",
    "IncomeStatementRepository",
    "SharePriceRepository",
    "TickerRepository",
]
