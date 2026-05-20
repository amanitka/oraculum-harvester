from datetime import date
from typing import Protocol

from common.domain.income_statement import IncomeStatementTemplate, StatementVariant


class DataTools(Protocol):
    """
    Read-only callable tools available to the analysis orchestrator for fetching
    data to inject into agent prompts.

    This interface abstracts away the underlying database repositories, ensuring
    agents have no persistence concerns.
    """

    async def get_ticker_profile(self, ticker: str) -> dict[str, str] | None:
        """Fetch basic ticker information (industry, sector, name)."""
        ...

    async def resolve_template(self, ticker: str) -> IncomeStatementTemplate:
        """
        Maps a ticker's industry/sector to a specific SimFin statement template.
        Falls back to 'general' if unknown.
        """
        ...

    def get_income_statement_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        """Returns income statement history formatted as a Markdown table."""
        ...

    def get_balance_sheet_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        """Returns balance sheet history formatted as a Markdown table."""
        ...

    def get_cash_flow_history(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        """Returns cash flow history formatted as a Markdown table."""
        ...

    def get_price_window(self, ticker: str, start: date, end: date) -> str:
        """Returns daily closing prices for a specific window as a Markdown table."""
        ...

    async def get_share_price_signals(self, ticker: str, market: str, as_of: date) -> str:
        """Returns recent daily and historical monthly share price signals as JSON."""
        ...

    def get_derived_metrics(
        self,
        ticker: str,
        *,
        template: IncomeStatementTemplate,
        variant: StatementVariant,
        limit: int = 100,
    ) -> str:
        """Returns derived metrics (ratios, per-share data) formatted as a Markdown table."""
        ...
