"""Bulk loads Parquet files into PostgreSQL staging tables."""

from __future__ import annotations

import logging
import time
from typing import Any, Callable

import pandas as pd
from sqlalchemy import text
from sqlmodel.ext.asyncio.session import AsyncSession

from analyst.infrastructure.models.run_log import IngestionRunLogDB
from common.domain.data_file_ready import DataFileReadyEvent

logger = logging.getLogger(__name__)


class ParquetLoader:
    """Orchestrates Parquet to PostgreSQL bulk loads."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def load(self, event: DataFileReadyEvent) -> None:
        """Load a Parquet file idempotently based on the event payload."""
        if await self._is_already_processed(event):
            logger.info(
                "Skipping already processed event: %s (run_id=%s)",
                event.dataset,
                event.run_id,
            )
            return

        start_time = time.monotonic()
        run_log = IngestionRunLogDB(
            dataset=event.dataset,
            run_id=event.run_id,
            file_checksum=event.file_checksum,
            status="RUNNING",
        )
        self._session.add(run_log)
        await self._session.commit()
        await self._session.refresh(run_log)

        try:
            loaded, merged = await self._process_dataset(event)
            run_log.status = "SUCCESS"
            run_log.loaded_rows = loaded
            run_log.merged_rows = merged
        except Exception as e:
            logger.exception("Failed to load dataset: %s", event.dataset)
            run_log.status = "FAILED"
            run_log.error_text = str(e)
            raise
        finally:
            run_log.duration_ms = int((time.monotonic() - start_time) * 1000)
            self._session.add(run_log)
            await self._session.commit()

    async def _is_already_processed(self, event: DataFileReadyEvent) -> bool:
        stmt = text(
            """
            SELECT 1 FROM t_ingestion_run_log
            WHERE dataset = :dataset AND run_id = :run_id AND file_checksum = :file_checksum AND status = 'SUCCESS'
            """
        )
        result = await self._session.exec(
            stmt,
            params={
                "dataset": event.dataset,
                "run_id": event.run_id,
                "file_checksum": event.file_checksum,
            },
        )
        return result.first() is not None

    async def _process_dataset(self, event: DataFileReadyEvent) -> tuple[int, int]:
        """Read Parquet, create staging, load, and merge. Returns (loaded, merged)."""
        df = pd.read_parquet(event.path, engine="pyarrow")
        if df.empty:
            return 0, 0

        # Replace NaN with None
        df = df.where(pd.notnull(df), None)
        records = df.to_dict(orient="records")

        stg_table = f"stg_{event.dataset}"

        # Dispatch to specific merge strategy
        strategies: dict[str, Callable[[str, list[dict[str, Any]]], Any]] = {
            "ticker": self._merge_ticker,
            "share_price": self._merge_share_price,
            "balance_sheet": self._merge_balance_sheet,
            "income_statement": self._merge_income_statement,
            "cash_flow_statement": self._merge_cash_flow_statement,
        }

        if event.dataset not in strategies:
            raise ValueError(f"Unknown dataset: {event.dataset}")

        await strategies[event.dataset](stg_table, records)

        return len(records), len(records)  # assuming all merged

    async def _merge_ticker(
        self, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        await self._session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_ticker INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )

        await self._session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                symbol, provider_id, provider_name, company_name, industry_id, industry_name,
                sector_name, isin, description, employee_count, market, currency, cik, extracted_at
            )
            VALUES (
                :symbol, :provider_id, :provider_name, :company_name, :industry_id, :industry_name,
                :sector_name, :isin, :description, :employee_count, :market, :currency, :cik, :extracted_at
            )
        """),
            records,
        )

        await self._session.exec(
            text(f"""
            INSERT INTO t_ticker (
                symbol, provider_id, provider_name, company_name, industry_id, industry_name,
                sector_name, isin, description, employee_count, market, currency, cik, extracted_at
            )
            SELECT symbol, provider_id, provider_name, company_name, industry_id, industry_name,
                   sector_name, isin, description, employee_count, market, currency, cik, extracted_at
            FROM {stg_table}
            ON CONFLICT (symbol, market) DO UPDATE SET
                provider_id = EXCLUDED.provider_id,
                provider_name = EXCLUDED.provider_name,
                company_name = EXCLUDED.company_name,
                industry_id = EXCLUDED.industry_id,
                industry_name = EXCLUDED.industry_name,
                sector_name = EXCLUDED.sector_name,
                isin = EXCLUDED.isin,
                description = EXCLUDED.description,
                employee_count = EXCLUDED.employee_count,
                currency = EXCLUDED.currency,
                cik = EXCLUDED.cik,
                extracted_at = EXCLUDED.extracted_at,
                updated_at = CURRENT_TIMESTAMP
        """)
        )

    async def _merge_share_price(
        self, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        await self._session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_share_price INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )

        await self._session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                ticker, sim_fin_id, currency, market, trade_date, open, high, low, close,
                adj_close, volume, shares_outstanding, dividend, extracted_at
            )
            VALUES (
                :ticker, :sim_fin_id, :currency, :market, :trade_date, :open, :high, :low, :close,
                :adj_close, :volume, :shares_outstanding, :dividend, :extracted_at
            )
        """),
            records,
        )

        await self._session.exec(
            text(f"""
            INSERT INTO t_share_price (
                ticker, sim_fin_id, currency, market, trade_date, open, high, low, close,
                adj_close, volume, shares_outstanding, dividend, extracted_at
            )
            SELECT ticker, sim_fin_id, currency, market, trade_date, open, high, low, close,
                   adj_close, volume, shares_outstanding, dividend, extracted_at
            FROM {stg_table}
            ON CONFLICT (ticker, market, trade_date) DO UPDATE SET
                sim_fin_id = EXCLUDED.sim_fin_id,
                currency = EXCLUDED.currency,
                open = EXCLUDED.open,
                high = EXCLUDED.high,
                low = EXCLUDED.low,
                close = EXCLUDED.close,
                adj_close = EXCLUDED.adj_close,
                volume = EXCLUDED.volume,
                shares_outstanding = EXCLUDED.shares_outstanding,
                dividend = EXCLUDED.dividend,
                extracted_at = EXCLUDED.extracted_at
        """)
        )

    async def _merge_balance_sheet(
        self, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        await self._session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_balance_sheet INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )

        # To avoid extremely long INSERT text, fetch columns dynamically or write explicit ones
        # We will write explicit ones based on the model since it's safer.
        await self._session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                shares_basic, shares_diluted, cash_and_equivalents, accounts_notes_receivable, total_assets, short_term_debt, long_term_debt,
                total_liabilities, share_capital_additional_paid_in, treasury_stock, retained_earnings, total_equity, total_liabilities_and_equity,
                property_plant_equipment_net, preferred_equity, inventories, total_current_assets, long_term_investments_receivables,
                other_long_term_assets, total_noncurrent_assets, payables_accruals, total_current_liabilities, total_noncurrent_liabilities,
                interbank_assets, short_and_long_term_investments, net_loans, net_fixed_assets, total_deposits, total_investments,
                insurance_reserves, policyholders_equity
            )
            VALUES (
                :template, :variant, :ticker, :simfin_id, :currency, :fiscal_year, :fiscal_period, :report_date, :publish_date, :restated_date, :extracted_at,
                :shares_basic, :shares_diluted, :cash_and_equivalents, :accounts_notes_receivable, :total_assets, :short_term_debt, :long_term_debt,
                :total_liabilities, :share_capital_additional_paid_in, :treasury_stock, :retained_earnings, :total_equity, :total_liabilities_and_equity,
                :property_plant_equipment_net, :preferred_equity, :inventories, :total_current_assets, :long_term_investments_receivables,
                :other_long_term_assets, :total_noncurrent_assets, :payables_accruals, :total_current_liabilities, :total_noncurrent_liabilities,
                :interbank_assets, :short_and_long_term_investments, :net_loans, :net_fixed_assets, :total_deposits, :total_investments,
                :insurance_reserves, :policyholders_equity
            )
        """),
            records,
        )

        await self._session.exec(
            text(f"""
            INSERT INTO t_balance_sheet (
                template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                shares_basic, shares_diluted, cash_and_equivalents, accounts_notes_receivable, total_assets, short_term_debt, long_term_debt,
                total_liabilities, share_capital_additional_paid_in, treasury_stock, retained_earnings, total_equity, total_liabilities_and_equity,
                property_plant_equipment_net, preferred_equity, inventories, total_current_assets, long_term_investments_receivables,
                other_long_term_assets, total_noncurrent_assets, payables_accruals, total_current_liabilities, total_noncurrent_liabilities,
                interbank_assets, short_and_long_term_investments, net_loans, net_fixed_assets, total_deposits, total_investments,
                insurance_reserves, policyholders_equity
            )
            SELECT * FROM {stg_table}
            ON CONFLICT (ticker, fiscal_year, fiscal_period, template, variant) DO UPDATE SET
                simfin_id = EXCLUDED.simfin_id,
                currency = EXCLUDED.currency,
                report_date = EXCLUDED.report_date,
                publish_date = EXCLUDED.publish_date,
                restated_date = EXCLUDED.restated_date,
                extracted_at = EXCLUDED.extracted_at,
                shares_basic = EXCLUDED.shares_basic,
                shares_diluted = EXCLUDED.shares_diluted,
                cash_and_equivalents = EXCLUDED.cash_and_equivalents,
                accounts_notes_receivable = EXCLUDED.accounts_notes_receivable,
                total_assets = EXCLUDED.total_assets,
                short_term_debt = EXCLUDED.short_term_debt,
                long_term_debt = EXCLUDED.long_term_debt,
                total_liabilities = EXCLUDED.total_liabilities,
                share_capital_additional_paid_in = EXCLUDED.share_capital_additional_paid_in,
                treasury_stock = EXCLUDED.treasury_stock,
                retained_earnings = EXCLUDED.retained_earnings,
                total_equity = EXCLUDED.total_equity,
                total_liabilities_and_equity = EXCLUDED.total_liabilities_and_equity,
                property_plant_equipment_net = EXCLUDED.property_plant_equipment_net,
                preferred_equity = EXCLUDED.preferred_equity,
                inventories = EXCLUDED.inventories,
                total_current_assets = EXCLUDED.total_current_assets,
                long_term_investments_receivables = EXCLUDED.long_term_investments_receivables,
                other_long_term_assets = EXCLUDED.other_long_term_assets,
                total_noncurrent_assets = EXCLUDED.total_noncurrent_assets,
                payables_accruals = EXCLUDED.payables_accruals,
                total_current_liabilities = EXCLUDED.total_current_liabilities,
                total_noncurrent_liabilities = EXCLUDED.total_noncurrent_liabilities,
                interbank_assets = EXCLUDED.interbank_assets,
                short_and_long_term_investments = EXCLUDED.short_and_long_term_investments,
                net_loans = EXCLUDED.net_loans,
                net_fixed_assets = EXCLUDED.net_fixed_assets,
                total_deposits = EXCLUDED.total_deposits,
                total_investments = EXCLUDED.total_investments,
                insurance_reserves = EXCLUDED.insurance_reserves,
                policyholders_equity = EXCLUDED.policyholders_equity
        """)
        )

    async def _merge_income_statement(
        self, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        await self._session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_income_statement INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )

        await self._session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                shares_basic, shares_diluted, revenue, operating_income, pretax_income, income_tax_benefit_net, income_continuing_ops,
                net_extraordinary_gains, net_income, net_income_common, non_operating_income, cost_of_revenue, gross_profit, operating_expenses,
                selling_general_admin, research_development, depreciation_amortization, interest_expense_net, pretax_income_adj,
                abnormal_gains_losses, provision_for_loan_losses, net_revenue_after_provisions, total_non_interest_expense, total_claims_losses,
                income_from_affiliates_net
            )
            VALUES (
                :template, :variant, :ticker, :simfin_id, :currency, :fiscal_year, :fiscal_period, :report_date, :publish_date, :restated_date, :extracted_at,
                :shares_basic, :shares_diluted, :revenue, :operating_income, :pretax_income, :income_tax_benefit_net, :income_continuing_ops,
                :net_extraordinary_gains, :net_income, :net_income_common, :non_operating_income, :cost_of_revenue, :gross_profit, :operating_expenses,
                :selling_general_admin, :research_development, :depreciation_amortization, :interest_expense_net, :pretax_income_adj,
                :abnormal_gains_losses, :provision_for_loan_losses, :net_revenue_after_provisions, :total_non_interest_expense, :total_claims_losses,
                :income_from_affiliates_net
            )
        """),
            records,
        )

        await self._session.exec(
            text(f"""
            INSERT INTO t_income_statement (
                template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                shares_basic, shares_diluted, revenue, operating_income, pretax_income, income_tax_benefit_net, income_continuing_ops,
                net_extraordinary_gains, net_income, net_income_common, non_operating_income, cost_of_revenue, gross_profit, operating_expenses,
                selling_general_admin, research_development, depreciation_amortization, interest_expense_net, pretax_income_adj,
                abnormal_gains_losses, provision_for_loan_losses, net_revenue_after_provisions, total_non_interest_expense, total_claims_losses,
                income_from_affiliates_net
            )
            SELECT * FROM {stg_table}
            ON CONFLICT (ticker, fiscal_year, fiscal_period, template, variant) DO UPDATE SET
                simfin_id = EXCLUDED.simfin_id,
                currency = EXCLUDED.currency,
                report_date = EXCLUDED.report_date,
                publish_date = EXCLUDED.publish_date,
                restated_date = EXCLUDED.restated_date,
                extracted_at = EXCLUDED.extracted_at,
                shares_basic = EXCLUDED.shares_basic,
                shares_diluted = EXCLUDED.shares_diluted,
                revenue = EXCLUDED.revenue,
                operating_income = EXCLUDED.operating_income,
                pretax_income = EXCLUDED.pretax_income,
                income_tax_benefit_net = EXCLUDED.income_tax_benefit_net,
                income_continuing_ops = EXCLUDED.income_continuing_ops,
                net_extraordinary_gains = EXCLUDED.net_extraordinary_gains,
                net_income = EXCLUDED.net_income,
                net_income_common = EXCLUDED.net_income_common,
                non_operating_income = EXCLUDED.non_operating_income,
                cost_of_revenue = EXCLUDED.cost_of_revenue,
                gross_profit = EXCLUDED.gross_profit,
                operating_expenses = EXCLUDED.operating_expenses,
                selling_general_admin = EXCLUDED.selling_general_admin,
                research_development = EXCLUDED.research_development,
                depreciation_amortization = EXCLUDED.depreciation_amortization,
                interest_expense_net = EXCLUDED.interest_expense_net,
                pretax_income_adj = EXCLUDED.pretax_income_adj,
                abnormal_gains_losses = EXCLUDED.abnormal_gains_losses,
                provision_for_loan_losses = EXCLUDED.provision_for_loan_losses,
                net_revenue_after_provisions = EXCLUDED.net_revenue_after_provisions,
                total_non_interest_expense = EXCLUDED.total_non_interest_expense,
                total_claims_losses = EXCLUDED.total_claims_losses,
                income_from_affiliates_net = EXCLUDED.income_from_affiliates_net
        """)
        )

    async def _merge_cash_flow_statement(
        self, stg_table: str, records: list[dict[str, Any]]
    ) -> None:
        await self._session.exec(
            text(f"""
            CREATE TEMP TABLE {stg_table} (LIKE t_cash_flow_statement INCLUDING DEFAULTS) ON COMMIT DROP;
        """)
        )

        await self._session.exec(
            text(f"""
            INSERT INTO {stg_table} (
                template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                shares_basic, shares_diluted, net_income_starting_line, depreciation_amortization, non_cash_items, net_cash_from_operating,
                change_in_fixed_assets_intangibles, net_cash_from_investing, dividends_paid, cash_from_repayment_of_debt,
                cash_from_repurchase_of_equity, net_cash_from_financing, net_change_in_cash, change_in_working_capital,
                net_cash_from_acquisitions_divestitures, effect_of_foreign_exchange_rates, change_in_accounts_receivable,
                change_in_inventories, change_in_accounts_payable, change_in_other, net_change_in_long_term_investment,
                provision_for_loan_losses, net_change_in_loans_interbank, net_change_in_investments
            )
            VALUES (
                :template, :variant, :ticker, :simfin_id, :currency, :fiscal_year, :fiscal_period, :report_date, :publish_date, :restated_date, :extracted_at,
                :shares_basic, :shares_diluted, :net_income_starting_line, :depreciation_amortization, :non_cash_items, :net_cash_from_operating,
                :change_in_fixed_assets_intangibles, :net_cash_from_investing, :dividends_paid, :cash_from_repayment_of_debt,
                :cash_from_repurchase_of_equity, :net_cash_from_financing, :net_change_in_cash, :change_in_working_capital,
                :net_cash_from_acquisitions_divestitures, :effect_of_foreign_exchange_rates, :change_in_accounts_receivable,
                :change_in_inventories, :change_in_accounts_payable, :change_in_other, :net_change_in_long_term_investment,
                :provision_for_loan_losses, :net_change_in_loans_interbank, :net_change_in_investments
            )
        """),
            records,
        )

        await self._session.exec(
            text(f"""
            INSERT INTO t_cash_flow_statement (
                template, variant, ticker, simfin_id, currency, fiscal_year, fiscal_period, report_date, publish_date, restated_date, extracted_at,
                shares_basic, shares_diluted, net_income_starting_line, depreciation_amortization, non_cash_items, net_cash_from_operating,
                change_in_fixed_assets_intangibles, net_cash_from_investing, dividends_paid, cash_from_repayment_of_debt,
                cash_from_repurchase_of_equity, net_cash_from_financing, net_change_in_cash, change_in_working_capital,
                net_cash_from_acquisitions_divestitures, effect_of_foreign_exchange_rates, change_in_accounts_receivable,
                change_in_inventories, change_in_accounts_payable, change_in_other, net_change_in_long_term_investment,
                provision_for_loan_losses, net_change_in_loans_interbank, net_change_in_investments
            )
            SELECT * FROM {stg_table}
            ON CONFLICT (ticker, fiscal_year, fiscal_period, template, variant) DO UPDATE SET
                simfin_id = EXCLUDED.simfin_id,
                currency = EXCLUDED.currency,
                report_date = EXCLUDED.report_date,
                publish_date = EXCLUDED.publish_date,
                restated_date = EXCLUDED.restated_date,
                extracted_at = EXCLUDED.extracted_at,
                shares_basic = EXCLUDED.shares_basic,
                shares_diluted = EXCLUDED.shares_diluted,
                net_income_starting_line = EXCLUDED.net_income_starting_line,
                depreciation_amortization = EXCLUDED.depreciation_amortization,
                non_cash_items = EXCLUDED.non_cash_items,
                net_cash_from_operating = EXCLUDED.net_cash_from_operating,
                change_in_fixed_assets_intangibles = EXCLUDED.change_in_fixed_assets_intangibles,
                net_cash_from_investing = EXCLUDED.net_cash_from_investing,
                dividends_paid = EXCLUDED.dividends_paid,
                cash_from_repayment_of_debt = EXCLUDED.cash_from_repayment_of_debt,
                cash_from_repurchase_of_equity = EXCLUDED.cash_from_repurchase_of_equity,
                net_cash_from_financing = EXCLUDED.net_cash_from_financing,
                net_change_in_cash = EXCLUDED.net_change_in_cash,
                change_in_working_capital = EXCLUDED.change_in_working_capital,
                net_cash_from_acquisitions_divestitures = EXCLUDED.net_cash_from_acquisitions_divestitures,
                effect_of_foreign_exchange_rates = EXCLUDED.effect_of_foreign_exchange_rates,
                change_in_accounts_receivable = EXCLUDED.change_in_accounts_receivable,
                change_in_inventories = EXCLUDED.change_in_inventories,
                change_in_accounts_payable = EXCLUDED.change_in_accounts_payable,
                change_in_other = EXCLUDED.change_in_other,
                net_change_in_long_term_investment = EXCLUDED.net_change_in_long_term_investment,
                provision_for_loan_losses = EXCLUDED.provision_for_loan_losses,
                net_change_in_loans_interbank = EXCLUDED.net_change_in_loans_interbank,
                net_change_in_investments = EXCLUDED.net_change_in_investments
        """)
        )
