"""SQLModel table declarations."""

from analyst.infrastructure.models.balance_sheet import BalanceSheetDB
from analyst.infrastructure.models.cash_flow_statement import CashFlowStatementDB
from analyst.infrastructure.models.derived import DerivedDB
from analyst.infrastructure.models.income_statement import IncomeStatementDB
from analyst.infrastructure.models.run_log import IngestionRunLogDB
from analyst.infrastructure.models.share_price import SharePriceDB
from analyst.infrastructure.models.ticker import TickerDB

__all__ = [
    "BalanceSheetDB",
    "CashFlowStatementDB",
    "DerivedDB",
    "IncomeStatementDB",
    "IngestionRunLogDB",
    "SharePriceDB",
    "TickerDB",
]
