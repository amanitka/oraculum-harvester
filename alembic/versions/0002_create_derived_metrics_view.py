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
CREATE OR REPLACE VIEW v_derived_metrics AS 
WITH statement_values AS (SELECT
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
					         NULLIF(income.payload ->> 'Revenue'::text, ''::text)::double precision AS revenue,
						     NULLIF(income.payload ->> 'Cost of Revenue'::text, ''::text)::double precision AS cost_of_revenue,
						     NULLIF(income.payload ->> 'Net Income'::text, ''::text)::double precision AS net_income,
						     NULLIF(income.payload ->> 'Operating Income (Loss)'::text, ''::text)::double precision AS operating_income,
						     NULLIF(income.payload ->> 'Interest Expense, Net'::text, ''::text)::double precision AS interest_expense_net,
						     NULLIF(income.payload ->> 'Income Tax (Expense) Benefit, Net'::text, ''::text)::double precision AS income_tax,
						     NULLIF(income.payload ->> 'Depreciation & Amortization'::text, ''::text)::double precision AS depreciation_amortization,
						     NULLIF(balance.payload ->> 'Total Equity'::text, ''::text)::double precision AS total_equity,
						     NULLIF(balance.payload ->> 'Total Current Assets'::text, ''::text)::double precision AS total_current_assets,
						     NULLIF(balance.payload ->> 'Total Current Liabilities'::text, ''::text)::double precision AS total_current_liabilities,
						     NULLIF(balance.payload ->> 'Total Liabilities'::text, ''::text)::double precision AS total_liabilities,
						     NULLIF(balance.payload ->> 'Cash, Cash Equivalents & Short Term Investments'::text, ''::text)::double precision AS cash_equivalents_short_term_investments,
						     NULLIF(balance.payload ->> 'Accounts & Notes Receivable'::text, ''::text)::double precision AS accounts_notes_receivable,
						     NULLIF(balance.payload ->> 'Inventories'::text, ''::text)::double precision AS inventories,
						     NULLIF(income.payload ->> 'Shares (Basic)'::text, ''::text)::double precision AS shares_basic,
						     NULLIF(income.payload ->> 'Shares (Diluted)'::text, ''::text)::double precision AS shares_diluted,
						     NULLIF(cash_flow.payload ->> 'Net Cash from Operating Activities'::text, ''::text)::double precision AS net_cash_from_operating_activities,
						     NULLIF(cash_flow.payload ->> 'Change in Fixed Assets & Intangibles'::text, ''::text)::double precision AS capital_expenditures
					      FROM t_income_statement income
					      LEFT JOIN t_balance_sheet balance ON balance.ticker = income.ticker
					                                       AND balance.simfin_id = income.simfin_id 
					                                    	AND balance.currency = income.currency
					                                    	AND balance.template = income.template
					                                    	AND balance.variant = income.variant
					                                    	AND balance.fiscal_year = income.fiscal_year 
					                                    	AND CASE WHEN balance.variant = 'annual' THEN 'FY' ELSE balance.fiscal_period END = income.fiscal_period
					      LEFT JOIN t_cash_flow_statement cash_flow ON cash_flow.ticker = income.ticker
					                                               AND cash_flow.simfin_id = income.simfin_id 
					                                               AND cash_flow.currency = income.currency
					                                               AND cash_flow.template = income.template 
					                                               AND cash_flow.variant = income.variant
					                                               AND cash_flow.fiscal_year = income.fiscal_year 
					                                               AND cash_flow.fiscal_period = income.fiscal_period
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
   -- =========================================================================
   -- 1. VALUATION & CASH METRICS
   -- =========================================================================
   -- EBITDA (Sign protected)
   COALESCE(operating_income, 0::double precision) + ABS(COALESCE(depreciation_amortization, 0::double precision)) AS ebitda,
   -- FREE CASH FLOW
   COALESCE(net_cash_from_operating_activities, 0::double precision) + COALESCE(capital_expenditures, 0::double precision) AS free_cash_flow,
   -- NCAV (Net Current Asset Value)
   COALESCE(total_current_assets, 0::double precision) - ABS(COALESCE(total_liabilities, 0::double precision)) AS ncav,
   -- NNWC (Net-Net Working Capital)
   COALESCE(cash_equivalents_short_term_investments, 0::double precision) 
     + (COALESCE(accounts_notes_receivable, 0::double precision) * 0.75::double precision) 
     + (COALESCE(inventories, 0::double precision) * 0.5::double precision) 
     - ABS(COALESCE(total_liabilities, 0::double precision)) AS net_net_working_capital,
   -- =========================================================================
   -- 2. CAPITAL EFFICIENCY & MARGIN METRICS
   -- =========================================================================
   -- ROCE (Return on Capital Employed) - Total Assets proxy: (Equity + Liabilities)
   operating_income / NULLIF((total_equity + ABS(COALESCE(total_liabilities, 0::double precision))), 0::double precision) AS return_on_capital_employed,
   -- ROE (Return on Equity)
   net_income / NULLIF(total_equity, 0::double precision) AS return_on_equity,
   -- ROA (Return on Assets)
   net_income / NULLIF((total_equity + ABS(COALESCE(total_liabilities, 0::double precision))), 0::double precision) AS return_on_assets,
   -- NET MARGIN
   net_income / NULLIF(revenue, 0::double precision) AS net_margin,
   -- =========================================================================
   -- 3. SOLVENCY, LIQUIDITY & EFFICIENCY METRICS
   -- =========================================================================
   -- CURRENT RATIO
   total_current_assets / NULLIF(ABS(COALESCE(total_current_liabilities, 0::double precision)), 0::double precision) AS current_ratio,
   -- DEBT TO EQUITY
   ABS(COALESCE(total_liabilities, 0::double precision)) / NULLIF(total_equity, 0::double precision) AS debt_to_equity,
   -- INVENTORY TURNOVER (Forces negative cost_of_revenue to absolute positive)
   ABS(COALESCE(cost_of_revenue, 0::double precision)) / NULLIF(inventories, 0::double precision) AS inventory_turnover,
   -- ASSET TURNOVER
   revenue / NULLIF((total_equity + ABS(COALESCE(total_liabilities, 0::double precision))), 0::double precision) AS asset_turnover,
   -- =========================================================================
   -- 4. PER SHARE & RAW BASE DATA FIELDS
   -- =========================================================================
   COALESCE(shares_diluted, shares_basic) AS shares_stabilized,
   -- EPS (Earnings Per Share)
   net_income / NULLIF(COALESCE(shares_diluted, shares_basic), 0::double precision) AS earnings_per_share,
   -- FCF Per Share
   (COALESCE(net_cash_from_operating_activities, 0::double precision) + COALESCE(capital_expenditures, 0::double precision)) 
     / NULLIF(COALESCE(shares_diluted, shares_basic), 0::double precision) AS fcf_per_share,
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