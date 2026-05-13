"""Create derived metrics SQL view

Revision ID: 0002_create_derived_metrics_view
Revises: 0001_initial
Create Date: 2026-05-13 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_create_derived_metrics_view"
down_revision: Union[str, Sequence[str], None] = "0001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DERIVED_JOIN_COLUMNS: tuple[str, ...] = (
    "ticker",
    "simfin_id",
    "currency",
    "template",
    "variant",
    "fiscal_year",
    "fiscal_period",
    "report_date",
    "publish_date",
)

_DERIVED_METRICS_VIEW_SQL = """
CREATE VIEW v_derived_metrics AS
WITH statement_values AS (
    SELECT
        income.composite_key,
        income.ticker,
        income.simfin_id,
        income.currency,
        income.template,
        income.variant,
        income.fiscal_year,
        income.fiscal_period,
        income.report_date,
        income.publish_date,
        income.restated_date,
        NULLIF(income.payload ->> 'Revenue', '')::double precision AS revenue,
        NULLIF(income.payload ->> 'Net Income', '')::double precision AS net_income,
        NULLIF(income.payload ->> 'Interest Expense, Net', '')::double precision AS interest_expense_net,
        NULLIF(income.payload ->> 'Income Tax (Expense) Benefit, Net', '')::double precision AS income_tax,
        NULLIF(income.payload ->> 'Depreciation & Amortization', '')::double precision AS depreciation_amortization,
        NULLIF(balance.payload ->> 'Total Equity', '')::double precision AS total_equity,
        NULLIF(balance.payload ->> 'Total Current Assets', '')::double precision AS total_current_assets,
        NULLIF(balance.payload ->> 'Total Liabilities', '')::double precision AS total_liabilities,
        NULLIF(balance.payload ->> 'Cash, Cash Equivalents & Short Term Investments', '')::double precision AS cash_equivalents_short_term_investments,
        NULLIF(balance.payload ->> 'Accounts & Notes Receivable', '')::double precision AS accounts_notes_receivable,
        NULLIF(balance.payload ->> 'Inventories', '')::double precision AS inventories,
        NULLIF(income.payload ->> 'Shares (Basic)', '')::double precision AS shares_basic,
        NULLIF(income.payload ->> 'Shares (Diluted)', '')::double precision AS shares_diluted,
        NULLIF(cash_flow.payload ->> 'Net Cash from Operating Activities', '')::double precision AS net_cash_from_operating_activities,
        NULLIF(cash_flow.payload ->> 'Change in Fixed Assets & Intangibles', '')::double precision AS capital_expenditures
    FROM t_income_statement AS income
    INNER JOIN t_balance_sheet AS balance
        ON balance.ticker = income.ticker
        AND balance.simfin_id = income.simfin_id
        AND balance.currency = income.currency
        AND balance.template = income.template
        AND balance.variant = income.variant
        AND balance.fiscal_year = income.fiscal_year
        AND balance.fiscal_period = income.fiscal_period
        AND balance.report_date = income.report_date
        AND balance.publish_date = income.publish_date
        AND balance.restated_date IS NOT DISTINCT FROM income.restated_date
    INNER JOIN t_cash_flow_statement AS cash_flow
        ON cash_flow.ticker = income.ticker
        AND cash_flow.simfin_id = income.simfin_id
        AND cash_flow.currency = income.currency
        AND cash_flow.template = income.template
        AND cash_flow.variant = income.variant
        AND cash_flow.fiscal_year = income.fiscal_year
        AND cash_flow.fiscal_period = income.fiscal_period
        AND cash_flow.report_date = income.report_date
        AND cash_flow.publish_date = income.publish_date
        AND cash_flow.restated_date IS NOT DISTINCT FROM income.restated_date
)
SELECT
    composite_key,
    ticker,
    simfin_id,
    currency,
    template,
    variant,
    fiscal_year,
    fiscal_period,
    report_date,
    publish_date,
    restated_date,
    net_income
        - COALESCE(interest_expense_net, 0)
        - COALESCE(income_tax, 0)
        + COALESCE(depreciation_amortization, 0) AS ebitda,
    COALESCE(net_cash_from_operating_activities, 0)
        + COALESCE(capital_expenditures, 0) AS free_cash_flow,
    total_current_assets - total_liabilities AS ncav,
    COALESCE(cash_equivalents_short_term_investments, 0)
        + COALESCE(accounts_notes_receivable, 0) * 0.75
        + COALESCE(inventories, 0) * 0.5
        - COALESCE(total_liabilities, 0) AS net_net_working_capital,
    COALESCE(shares_diluted, shares_basic) AS shares_stabilized,
    net_income / NULLIF(total_equity, 0) AS return_on_equity,
    net_income / NULLIF(revenue, 0) AS net_margin,
    revenue,
    net_income
FROM statement_values;
"""


def upgrade() -> None:
    """Upgrade schema."""
    _create_statement_join_indexes()
    op.execute(sa.text(_DERIVED_METRICS_VIEW_SQL))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DROP VIEW IF EXISTS v_derived_metrics"))
    _drop_statement_join_indexes()


def _create_statement_join_indexes() -> None:
    """Create statement indexes used by the derived metrics view."""
    for table_name in _statement_tables():
        op.create_index(
            f"ix_{table_name}_derived_join",
            table_name,
            list(_DERIVED_JOIN_COLUMNS),
            unique=False,
        )


def _drop_statement_join_indexes() -> None:
    """Drop statement indexes used by the derived metrics view."""
    for table_name in _statement_tables():
        op.drop_index(f"ix_{table_name}_derived_join", table_name=table_name)


def _statement_tables() -> tuple[str, ...]:
    """Return statement tables participating in derived metrics."""
    return (
        "t_income_statement",
        "t_balance_sheet",
        "t_cash_flow_statement",
    )
