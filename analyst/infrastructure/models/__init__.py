"""SQLModel tables owned by the analyst service.

Importing this package registers every `XxxDB` class with
`SQLModel.metadata`, which is how Alembic autogenerate discovers them.
Add new aggregates here as they are introduced.
"""

from analyst.infrastructure.models.balance_sheet import BalanceSheetDB
from analyst.infrastructure.models.cash_flow_statement import CashFlowStatementDB
from analyst.infrastructure.models.income_statement import IncomeStatementDB
from analyst.infrastructure.models.run_log import IngestionRunLogDB
from analyst.infrastructure.models.ticker import TickerDB

__all__ = [
    "BalanceSheetDB",
    "CashFlowStatementDB",
    "IncomeStatementDB",
    "IngestionRunLogDB",
    "TickerDB",
]
