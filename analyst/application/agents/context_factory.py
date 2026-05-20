from datetime import date, timedelta
import json

from sqlmodel import select
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.application.agents.tools import DataTools
from analyst.infrastructure.models.industry import IndustryDB
from analyst.infrastructure.repositories.balance_sheet import BalanceSheetRepository
from analyst.infrastructure.repositories.cash_flow_statement import CashFlowStatementRepository
from analyst.infrastructure.repositories.daily_market_signals import (
    DailyMarketSignalsQuery,
    DailyMarketSignalsRepository,
)
from analyst.infrastructure.repositories.derived_metrics import (
    DerivedMetricsRepository,
    DerivedMetricsQuery,
)
from analyst.infrastructure.repositories.income_statement import IncomeStatementRepository
from analyst.infrastructure.repositories.share_price import SharePriceRepository
from analyst.infrastructure.repositories.ticker import TickerRepository
from common.domain.income_statement import IncomeStatementTemplate, StatementVariant


class AgentDataTools(DataTools):
    """
    Concrete implementation of DataTools that delegates to the underlying
    database repositories.
    """

    def __init__(self, session: AsyncSession):
        self._session = session
        self._ticker_repo = TickerRepository(session)
        self._income_repo = IncomeStatementRepository(session)
        self._balance_sheet_repo = BalanceSheetRepository(session)
        self._cash_flow_repo = CashFlowStatementRepository(session)
        self._share_price_repo = SharePriceRepository(session)
        self._derived_metrics_repo = DerivedMetricsRepository(session)
        self._signals_repo = DailyMarketSignalsRepository(session)

    def _to_markdown(self, items: list, title: str | None = None) -> str:
        """Converts a list of Pydantic models or dicts to a Markdown table."""
        if not items:
            return "No data available."

        # Use model_dump() for Pydantic models to get dict representation
        if hasattr(items[0], "model_dump"):
            dict_items = [item.model_dump() for item in items]
            headers = list(dict_items[0].keys())
        elif isinstance(items[0], dict):
            dict_items = items
            headers = list(dict_items[0].keys())
        else:
            return "Cannot generate Markdown for unsupported data type."

        # Exclude redundant columns from the table body
        excluded_headers = ["template", "variant"]
        display_headers = [h for h in headers if h not in excluded_headers]

        header_line = f"| {' | '.join(display_headers)} |"
        separator = f"| {' | '.join(['---'] * len(display_headers))} |"

        rows = []
        for item in dict_items:
            row_values = [str(item.get(h, "")) for h in display_headers]
            rows.append(f"| {' | '.join(row_values)} |")

        title_line = f"### {title}\n" if title else ""
        return title_line + "\n".join([header_line, separator] + rows)

    async def get_ticker_profile(self, ticker: str) -> dict[str, str] | None:
        db_ticker = await self._ticker_repo.get_by_ticker(ticker)
        if not db_ticker:
            return None
        return {
            "ticker": db_ticker.ticker,
            "name": db_ticker.company_name or "Unknown",
            "industry": db_ticker.industry_name or "Unknown",
            "sector": db_ticker.sector_name or "Unknown",
            "industry_id": str(db_ticker.industry_id) if db_ticker.industry_id else "",
        }

    async def resolve_template(self, ticker: str) -> IncomeStatementTemplate:
        profile = await self.get_ticker_profile(ticker)
        if not profile or not profile.get("industry_id"):
            return "general"

        try:
            industry_id = int(profile["industry_id"])
        except (ValueError, TypeError):
            return "general"

        statement = select(IndustryDB).where(IndustryDB.industry_id == industry_id)

        def _run_sync_query(sync_session):
            return sync_session.execute(statement).scalar_one_or_none()

        industry_db = await self._session.run_sync(_run_sync_query)

        if industry_db:
            return industry_db.statement_template

        return "general"

    async def get_income_statement_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        history = await self._income_repo.fetch_ticker_history(
            ticker=ticker, template=template, variant=variant, limit=limit
        )
        title = f"Income Statement History for {ticker} ({variant.upper()})"
        return self._to_markdown(history, title=title)

    async def get_balance_sheet_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        history = await self._balance_sheet_repo.fetch_ticker_history(
            ticker=ticker, template=template, variant=variant, limit=limit
        )
        title = f"Balance Sheet History for {ticker} ({variant.upper()})"
        return self._to_markdown(history, title=title)

    async def get_cash_flow_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        history = await self._cash_flow_repo.fetch_ticker_history(
            ticker=ticker, template=template, variant=variant, limit=limit
        )
        title = f"Cash Flow History for {ticker} ({variant.upper()})"
        return self._to_markdown(history, title=title)

    async def get_price_window(self, ticker: str, start: date, end: date) -> str:
        prices = await self._share_price_repo.fetch_prices(
            ticker=ticker, start_date=start, end_date=end
        )
        title = f"Share Prices for {ticker} from {start} to {end}"
        return self._to_markdown(prices, title=title)

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
            "historical_monthly": [row.model_dump(exclude_none=True) for row in monthly_results],
        }
        return json.dumps(data, default=_serialize_date)

    async def get_derived_metrics(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        query = DerivedMetricsQuery(
            ticker=ticker, template=template, variant=variant, limit=limit
        )
        metrics = await self._derived_metrics_repo.fetch(query)
        title = f"Derived Metrics for {ticker} ({template.upper()}/{variant.upper()})"
        return self._to_markdown(metrics, title=title)


class AgentContextFactory:
    """
    Factory for creating the read-only tools required by the analysis workflow.
    """

    def __init__(self, session: AsyncSession):
        self._session = session

    def create_tools(self) -> DataTools:
        return AgentDataTools(self._session)
