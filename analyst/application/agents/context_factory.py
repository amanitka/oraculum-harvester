from datetime import date
from typing import Protocol

from sqlalchemy.orm import Session

from analyst.application.agents.tools import DataTools
from analyst.infrastructure.repositories.balance_sheet import BalanceSheetRepository
from analyst.infrastructure.repositories.cash_flow_statement import CashFlowStatementRepository
from analyst.infrastructure.repositories.derived_metrics import DerivedMetricsRepository
from analyst.infrastructure.repositories.income_statement import IncomeStatementRepository
from analyst.infrastructure.repositories.share_price import SharePriceRepository
from analyst.infrastructure.repositories.ticker import TickerRepository
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant


class AgentDataTools(DataTools):
    """
    Concrete implementation of DataTools that delegates to the underlying
    database repositories.
    """

    def __init__(self, session: Session):
        self._ticker_repo = TickerRepository(session)
        self._income_repo = IncomeStatementRepository(session)
        self._balance_sheet_repo = BalanceSheetRepository(session)
        self._cash_flow_repo = CashFlowStatementRepository(session)
        self._share_price_repo = SharePriceRepository(session)
        self._derived_metrics_repo = DerivedMetricsRepository(session)

    def get_ticker_profile(self, ticker: str) -> dict[str, str] | None:
        db_ticker = self._ticker_repo.get_by_ticker(ticker)
        if not db_ticker:
            return None
        return {
            "ticker": db_ticker.ticker,
            "name": db_ticker.name or "Unknown",
            "industry": db_ticker.industry_name or "Unknown",
            "sector": db_ticker.sector_name or "Unknown",
        }

    def resolve_template(self, ticker: str) -> IncomeStatementTemplate:
        # In a real implementation, this would map the industry/sector string
        # from the ticker profile to one of the three templates.
        # This mapping should ideally reside in a configuration or a dedicated mapper class.
        
        # For this phase, a simple static mapping or a default to "general" is sufficient
        # to prove the wiring works.
        profile = self.get_ticker_profile(ticker)
        if not profile:
            return "general"
            
        industry = profile.get("industry", "").lower()
        if "bank" in industry:
            return "banks"
        if "insurance" in industry:
            return "insurance"
            
        return "general"

    def get_income_statement_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        rows = self._income_repo.get_history(ticker, limit=limit)
        # Note: A real implementation would format the returned models into a Markdown table,
        # filtering by the requested variant.
        # We return a placeholder string for the wiring phase.
        return f"Income Statement History for {ticker} ({variant})"

    def get_balance_sheet_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        rows = self._balance_sheet_repo.get_history(ticker, limit=limit)
        return f"Balance Sheet History for {ticker} ({variant})"

    def get_cash_flow_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        rows = self._cash_flow_repo.get_history(ticker, limit=limit)
        return f"Cash Flow History for {ticker} ({variant})"

    def get_price_window(self, ticker: str, start: date, end: date) -> str:
        rows = self._share_price_repo.get_window(ticker, start, end)
        return f"Share Prices for {ticker} from {start} to {end}"

    def get_derived_metrics(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        # Note: DerivedMetricsRepository uses an async fetch method with DerivedMetricsQuery.
        # This requires an async session. For now, we mock the return for wiring.
        return f"Derived Metrics for {ticker} ({template}/{variant})"


class AgentContextFactory:
    """
    Factory for creating the read-only tools required by the analysis workflow.
    """

    def __init__(self, session: Session):
        self._session = session

    def create_tools(self) -> DataTools:
        return AgentDataTools(self._session)
