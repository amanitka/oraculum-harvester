"""SQLModel table declarations."""

from analyst.infrastructure.models.balance_sheet import BalanceSheetDB
from analyst.infrastructure.models.cash_flow_statement import CashFlowStatementDB
from analyst.infrastructure.models.daily_market_signals import DailyMarketSignalDB
from analyst.infrastructure.models.derived_metrics import DerivedMetricsDB
from analyst.infrastructure.models.income_statement import IncomeStatementDB
from analyst.infrastructure.models.run_log import IngestionRunLogDB
from analyst.infrastructure.models.share_price import SharePriceDB
from analyst.infrastructure.models.ticker import TickerDB

__all__ = [
    "BalanceSheetDB",
    "CashFlowStatementDB",
    "DailyMarketSignalDB",
    "DerivedMetricsDB",
    "IncomeStatementDB",
    "IngestionRunLogDB",
    "SharePriceDB",
    "TickerDB",
]
