"""Create daily market signals SQL view.

Revision ID: 0006_daily_market_signals
Revises: 0005
Create Date: 2026-05-19 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0006_daily_market_signals"
down_revision: Union[str, Sequence[str], None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_DAILY_MARKET_SIGNALS_VIEW_SQL = """
                                 CREATE
                                 OR REPLACE VIEW v_daily_market_signals AS
WITH fundamental_timeline AS (SELECT 
							     ticker,
							     simfin_id,
							     currency,
							     fiscal_year,
							     fiscal_period,
							     publish_date AS valid_from,
							     LEAD(publish_date, 1, '9999-12-31'::date) OVER (
							         PARTITION BY ticker 
							         ORDER BY publish_date ASC, restated_date ASC
							     ) AS valid_to,
							     revenue,
							     net_income,
							     ebitda,
							     free_cash_flow,
							     ncav,
							     net_net_working_capital,
							     return_on_capital_employed,
							     return_on_equity,
							     return_on_assets,
							     net_margin,
							     current_ratio,
							     debt_to_equity,
							     shares_stabilized,
							     earnings_per_share,
							     fcf_per_share,
							     -- Pulling base variables directly to avoid division hacks in the daily outer select
							     (net_income / NULLIF(return_on_equity, 0)) AS derived_total_equity,
							     (revenue / NULLIF(asset_turnover, 0)) AS derived_total_assets
							  FROM v_derived_metrics
							  WHERE variant = 'ttm' 
							    AND publish_date IS NOT NULL
                              ),
     share_price AS (SELECT 
					    p.*,
					    AVG(p.close) OVER (PARTITION BY p.ticker ORDER BY p.trade_date ROWS BETWEEN 49 PRECEDING AND CURRENT ROW) AS ma_50,
					    AVG(p.close) OVER (PARTITION BY p.ticker ORDER BY p.trade_date ROWS BETWEEN 199 PRECEDING AND CURRENT ROW) AS ma_200,
					    AVG(p.volume) OVER (PARTITION BY p.ticker ORDER BY p.trade_date ROWS BETWEEN 29 PRECEDING AND CURRENT ROW) AS vol_30
					 FROM public.t_share_price p
                     )
                                 SELECT
                                     -- Context Keys
                                     p.trade_date,
                                     CASE
                                         WHEN p.trade_date = MAX(p.trade_date) OVER (PARTITION BY p.ticker, DATE_TRUNC('month', p.trade_date)) THEN 'Y'
                                         ELSE 'N'
                                         END                                                         AS flag_last_day_of_month,
                                     p.ticker,
                                     p.market,
                                     p.currency,
                                     -- Core Market Pricing & Technical Momentum
                                     p.close                                                         AS share_price,
                                     p.volume,
                                     ROUND(((p.close - p.ma_50) / NULLIF(p.ma_50, 0) * 100):: numeric,
                                           2)                                                        AS pct_from_50d_ma,
                                     ROUND(((p.close - p.ma_200) / NULLIF(p.ma_200, 0) * 100):: numeric,
                                           2)                                                        AS pct_from_200d_ma,
                                     ROUND((p.volume / NULLIF(p.vol_30, 0)):: numeric, 2)            AS volume_velocity,
                                     -- Fundamental Context
                                     f.fiscal_year                                                   AS active_fiscal_year,
                                     f.fiscal_period                                                 AS active_fiscal_period,
                                     f.valid_from                                                    AS active_report_publish_date,
                                     -- 1. Valuation & Size Metrics
                                     (p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) AS market_capitalization,
                                     p.close / NULLIF(f.earnings_per_share, 0)                       AS pe_ratio,
                                     f.earnings_per_share / NULLIF(p.close, 0)                       AS earnings_yield,
                                     p.close / NULLIF(f.fcf_per_share, 0)                            AS price_to_fcf,
                                     (p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) /
                                     NULLIF(f.revenue, 0)                                            AS price_to_sales,
                                     (p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) /
                                     NULLIF(f.derived_total_equity, 0)                               AS price_to_book,
                                     -- 2. Deep Value Graham Signals
                                     (p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) /
                                     NULLIF(f.ncav, 0)                                               AS price_to_ncav,
                                     (p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) /
                                     NULLIF(f.net_net_working_capital, 0)                            AS price_to_nnwc,
                                     CASE
                                         WHEN (p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) <
                                              f.net_net_working_capital THEN 1
                                         ELSE 0
                                         END                                                         AS is_graham_net_net,
                                     -- 3. Enterprise Value (EV) Multiples (Corrected: Market Cap + Total Liabilities)
                                     -- Total Liabilities is computed as: Total Assets - Total Equity
                                     ((p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) +
                                      (f.derived_total_assets - f.derived_total_equity))             AS enterprise_value,
                                     ((p.close * COALESCE(p.shares_outstanding, f.shares_stabilized)) +
                                      (f.derived_total_assets - f.derived_total_equity))
                                         /
                                     NULLIF(f.ebitda, 0)                                             AS ev_to_ebitda,
                                     -- 4. Capital Efficiency
                                     f.return_on_capital_employed,
                                     f.return_on_equity,
                                     f.net_margin,
                                     -- 5. Solvency & Liquidity
                                     f.current_ratio,
                                     f.debt_to_equity
                                 FROM share_price p
                                          LEFT JOIN fundamental_timeline f ON p.ticker = f.ticker
                                     AND p.trade_date >= f.valid_from
                                     AND p.trade_date < f.valid_to; \
                                 """


def upgrade() -> None:
    """Upgrade schema."""
    op.execute(sa.text(_DAILY_MARKET_SIGNALS_VIEW_SQL))


def downgrade() -> None:
    """Downgrade schema."""
    op.execute(sa.text("DROP VIEW IF EXISTS v_daily_market_signals"))
