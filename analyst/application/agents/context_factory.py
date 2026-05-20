from datetime import date
from typing import Protocol

from sqlalchemy.orm import Session
from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.application.agents.tools import DataTools
from analyst.infrastructure.repositories.balance_sheet import BalanceSheetRepository
from analyst.infrastructure.repositories.cash_flow_statement import CashFlowStatementRepository
from analyst.infrastructure.repositories.derived_metrics import DerivedMetricsRepository
from analyst.infrastructure.repositories.income_statement import IncomeStatementRepository
from analyst.infrastructure.repositories.share_price import SharePriceRepository
from analyst.infrastructure.repositories.ticker import TickerRepository
from analyst.infrastructure.repositories.daily_market_signals import DailyMarketSignalsRepository, DailyMarketSignalsQuery
import json
from datetime import timedelta
from analyst.infrastructure.models.industry import IndustryDB
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant


class AgentDataTools(DataTools):
    """
    Concrete implementation of DataTools that delegates to the underlying
    database repositories.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._ticker_repo = TickerRepository(session)
        # The following repos are sync and need to be adapted or used with run_sync
        # For now, we will assume they can be adapted to work with the async session's sync_session
        self._income_repo = IncomeStatementRepository(session) # type: ignore
        self._balance_sheet_repo = BalanceSheetRepository(session) # type: ignore
        self._cash_flow_repo = CashFlowStatementRepository(session) # type: ignore
        self._share_price_repo = SharePriceRepository(session) # type: ignore
        self._derived_metrics_repo = DerivedMetricsRepository(session) # type: ignore
        self._signals_repo = DailyMarketSignalsRepository(session)

    async def get_ticker_profile(self, ticker: str) -> dict[str, str] | None:
        db_ticker = await self._ticker_repo.get_by_ticker(ticker)
        if not db_ticker:
            return None
        return {
            "ticker": db_ticker.ticker,
            "name": db_ticker.company_name or "Unknown",
            "industry": db_ticker.industry_name or "Unknown",
            "sector": db_ticker.sector_name or "Unknown",
            "industry_id": db_ticker.industry_id or "",
        }

    async def resolve_template(self, ticker: str) -> IncomeStatementTemplate:
        profile = await self.get_ticker_profile(ticker)
        if not profile or not profile.get("industry_id"):
            return "general"
            
        industry_id = profile["industry_id"]
        
        statement = select(IndustryDB).where(IndustryDB.industry_id == industry_id)
        
        def _run_sync_query(sync_session):
            return sync_session.execute(statement).scalar_one_or_none()

        industry_db = await self._session.run_sync(_run_sync_query)
        
        if industry_db:
            return industry_db.statement_template # type: ignore
            
        return "general"

    def get_income_statement_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        # This needs to be async or use run_sync
        return f"Income Statement History for {ticker} ({variant})"

    def get_balance_sheet_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        # This needs to be async or use run_sync
        return f"Balance Sheet History for {ticker} ({variant})"

    def get_cash_flow_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        # This needs to be async or use run_sync
        return f"Cash Flow History for {ticker} ({variant})"

    def get_price_window(self, ticker: str, start: date, end: date) -> str:
        # This needs to be async or use run_sync
        return f"Share Prices for {ticker} from {start} to {end}"

    async def get_share_price_signals(self, ticker: str, market: str, as_of: date) -> str:
        # Fetch last 30 days
        thirty_days_ago = as_of - timedelta(days=30)
        daily_query = DailyMarketSignalsQuery(
            ticker=ticker,
            market=market,
            from_date=thirty_days_ago,
            to_date=as_of,
            limit=30,
        )
        daily_results = await self._signals_repo.fetch(daily_query)

        # Fetch last 10 years monthly
        ten_years_ago = as_of.replace(year=as_of.year - 10)
        monthly_query = DailyMarketSignalsQuery(
            ticker=ticker,
            market=market,
            from_date=ten_years_ago,
            to_date=as_of,
            only_month_end=True,
            limit=120,
        )
        monthly_results = await self._signals_repo.fetch(monthly_query)

        def _serialize_date(obj):
            if isinstance(obj, date):
                return obj.isoformat()
            raise TypeError("Type not serializable")

        data = {
            "recent_daily": [row.model_dump(exclude_none=True) for row in daily_results],
            "historical_monthly": [row.model_dump(exclude_none=True) for row in monthly_results]
        }
        return json.dumps(data, default=_serialize_date)

    def get_derived_metrics(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        # This needs to be async or use run_sync
        return f"Derived Metrics for {ticker} ({template}/{variant})"


class AgentContextFactory:
    """
    Factory for creating the read-only tools required by the analysis workflow.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    def create_tools(self) -> DataTools:
        return AgentDataTools(self._session)
