"""Streamlit operations console for manual data-refresh commands."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date
from uuid import UUID

import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlmodel import select

from common.config import config
from common.messaging.kafka_publisher import KafkaRequestPublisher
from common.requests.base import Request
from application.refresh_request_factory import (
    STATEMENT_TEMPLATES,
    STATEMENT_VARIANTS,
    build_balance_sheet_request,
    build_cash_flow_statement_request,
    build_income_statement_request,
    build_share_price_request,
    build_ticker_request,
    build_market_request,
    build_industry_request,
)
from application.refresh_service import RefreshService
from application.analysis_trigger import AnalysisTrigger
from infrastructure.repositories.analysis import AnalysisRepository
from analyst.infrastructure.repositories.ticker import TickerRepository
from analyst.infrastructure.repositories.market import MarketRepository
from analyst.infrastructure.models.ticker import TickerDB

logger = logging.getLogger(__name__)

DEFAULT_MARKET = "us"
DEFAULT_PRICE_VARIANT = "daily"
DEFAULT_SAFETY_WINDOW_DAYS = 7


def _run_awaitable(awaitable: Awaitable[None]) -> None:
    """Execute one awaitable in a fresh event loop."""
    asyncio.run(awaitable)


def _trigger_request(request: Request) -> None:
    """Publish one refresh request and render the result in the UI."""
    service = RefreshService(KafkaRequestPublisher())
    with st.spinner("Publishing request to Kafka..."):
        _run_awaitable(service.trigger(request))
    st.success(f"Published `{request.request_type}`.")
    st.code(
        "\n".join(
            [
                f"correlation_id: {request.correlation_id}",
                f"issued_at: {request.issued_at.isoformat()}",
            ]
        )
    )


def _render_ticker_form() -> None:
    """Render the ticker refresh form."""
    st.subheader("Ticker refresh")
    with st.form("refresh_ticker_form"):
        market = st.text_input("Market", value=DEFAULT_MARKET)
        is_submitted = st.form_submit_button("Queue ticker refresh")
    if not is_submitted:
        return

    try:
        request = build_ticker_request(market)
        _trigger_request(request)
    except ValueError as error:
        st.error(str(error))
    except Exception:
        logger.exception("Failed to queue ticker refresh")
        st.error("Failed to queue ticker refresh. Check logs for details.")


def _render_metadata_form() -> None:
    """Render the market and industry refresh form."""
    st.subheader("Metadata refresh (Markets & Industries)")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Queue market refresh", width="stretch"):
            try:
                request = build_market_request()
                _trigger_request(request)
            except Exception:
                logger.exception("Failed to queue market refresh")
                st.error("Failed to queue market refresh. Check logs.")
    with col2:
        if st.button("Queue industry refresh", width="stretch"):
            try:
                request = build_industry_request()
                _trigger_request(request)
            except Exception:
                logger.exception("Failed to queue industry refresh")
                st.error("Failed to queue industry refresh. Check logs.")


def _render_share_price_form() -> None:
    """Render the share-price refresh form."""
    st.subheader("Share price refresh")
    with st.form("refresh_share_price_form"):
        market = st.text_input("Market", value=DEFAULT_MARKET, key="share_price_market")
        variant = st.text_input(
            "Variant",
            value=DEFAULT_PRICE_VARIANT,
            key="share_price_variant",
            help="Use SimFin variant name, for example `daily`.",
        )
        has_from_date = st.checkbox(
            "Use incremental from_date",
            value=True,
            key="share_price_has_from_date",
        )
        selected_from_date = st.date_input(
            "From date",
            value=date.today(),
            disabled=not has_from_date,
            key="share_price_from_date",
        )
        safety_window_days = int(
            st.number_input(
                "Safety window days",
                min_value=0,
                value=DEFAULT_SAFETY_WINDOW_DAYS,
                step=1,
                key="share_price_safety_window_days",
            )
        )
        is_submitted = st.form_submit_button("Queue share-price refresh")
    if not is_submitted:
        return

    from_date = selected_from_date if has_from_date else None
    try:
        request = build_share_price_request(
            market=market,
            variant=variant,
            from_date=from_date,
            safety_window_days=safety_window_days,
        )
        _trigger_request(request)
    except ValueError as error:
        st.error(str(error))
    except Exception:
        logger.exception("Failed to queue share-price refresh")
        st.error("Failed to queue share-price refresh. Check logs for details.")


def _render_statement_form(
    *,
    form_key: str,
    title: str,
    submit_label: str,
    build_request: Callable[[str, str, list[str]], Request],
    template_options: tuple[str, ...] = STATEMENT_TEMPLATES,
) -> None:
    """Render one fundamentals-statement refresh form."""
    st.subheader(title)
    with st.form(form_key):
        market = st.text_input("Market", value=DEFAULT_MARKET, key=f"{form_key}_market")
        variants = st.multiselect(
            "Variants",
            options=list(STATEMENT_VARIANTS),
            default=list(STATEMENT_VARIANTS),
            key=f"{form_key}_variants",
        )
        templates = st.multiselect(
            "Templates",
            options=list(template_options),
            default=list(template_options),
            key=f"{form_key}_templates",
        )
        is_submitted = st.form_submit_button(submit_label)
    if not is_submitted:
        return

    try:
        if not variants:
            raise ValueError("Select at least one variant.")

        for variant in variants:
            request = build_request(market, variant, templates)
            _trigger_request(request)
    except ValueError as error:
        st.error(str(error))
    except Exception:
        logger.exception("Failed to queue %s", title.lower())
        st.error(f"Failed to queue {title.lower()}. Check logs for details.")


def _render_refresh_tab() -> None:
    """Render the manual refresh controls."""
    st.caption(
        "Use these controls to queue refresh requests to Kafka. "
        "The harvester consumes them from the configured request topic."
    )
    metadata_tab, ticker_tab, share_price_tab, income_tab, balance_tab, cash_flow_tab = st.tabs(
        [
            "Metadata",
            "Ticker",
            "Share Price",
            "Income Statement",
            "Balance Sheet",
            "Cash Flow",
        ]
    )
    with metadata_tab:
        _render_metadata_form()
    with ticker_tab:
        _render_ticker_form()
    with share_price_tab:
        _render_share_price_form()
    with income_tab:
        _render_statement_form(
            form_key="refresh_income_statement_form",
            title="Income statement refresh",
            submit_label="Queue income-statement refresh",
            build_request=build_income_statement_request,
        )
    with balance_tab:
        _render_statement_form(
            form_key="refresh_balance_sheet_form",
            title="Balance sheet refresh",
            submit_label="Queue balance-sheet refresh",
            build_request=build_balance_sheet_request,
        )
    with cash_flow_tab:
        _render_statement_form(
            form_key="refresh_cash_flow_statement_form",
            title="Cash-flow statement refresh",
            submit_label="Queue cash-flow refresh",
            build_request=build_cash_flow_statement_request,
        )


def _render_analysis_tab() -> None:
    """Render the AI Analysis controls and results."""
    run_col, list_col = st.columns([1, 2])

    engine = create_engine(config.database_url)

    with run_col:
        st.subheader("Run new analysis")
        
        # We need a session to query markets and tickers
        with Session(engine) as session:
            # Get distinct markets from the ticker table directly
            # This ensures we only show markets that actually have tickers
            stmt_markets = select(TickerDB.market).distinct().order_by(TickerDB.market)
            available_markets = session.execute(stmt_markets).scalars().all()
            market_options = list(available_markets) if available_markets else ["us"]

            # The market selection happens *outside* the form so it triggers a re-render immediately
            # allowing the ticker selectbox to update its options.
            selected_market = st.selectbox(
                "Filter by Market (Optional)", 
                options=["All"] + market_options, # Provide an "All" option
                index=1 if "us" in market_options else 0 # Default to "us" if present
            )

            # Query tickers based on the selected market
            stmt_tickers = select(TickerDB).order_by(TickerDB.ticker.asc())
            if selected_market != "All":
                stmt_tickers = stmt_tickers.where(TickerDB.market == selected_market)
            
            tickers = session.execute(stmt_tickers).scalars().all()
            
            # Create a dictionary mapping the display string to the actual ticker object
            # e.g. "AAPL - Apple Inc." -> TickerDB
            ticker_options_map = {
                f"{t.ticker.upper()} - {t.company_name or 'Unknown'}": t 
                for t in tickers
            }

        with st.form("run_analysis_form"):
            # Provide the selectbox inside the form if tickers are available
            if ticker_options_map:
                selected_display = st.selectbox("Select Ticker", options=list(ticker_options_map.keys()))
                
                # We extract the actual ticker string and market from the mapped object
                if selected_display:
                    selected_ticker_obj = ticker_options_map[selected_display]
                    final_ticker = selected_ticker_obj.ticker
                    final_market = selected_ticker_obj.market
                else:
                    final_ticker = ""
                    final_market = ""
            else:
                st.info("No tickers found in the database. Please run a Ticker Refresh first.")
                final_ticker = st.text_input("Manual Ticker symbol", placeholder="AAPL")
                final_market = selected_market if selected_market != "All" else "us"

            is_submitted = st.form_submit_button("Analyze")

        if is_submitted:
            if not final_ticker:
                st.error("Please provide a ticker.")
            else:
                trigger = AnalysisTrigger(KafkaRequestPublisher())
                try:
                    # Clean inputs before sending
                    clean_ticker = final_ticker.strip().upper()
                    clean_market = final_market.strip().lower()
                    
                    cid = trigger.trigger_analysis(clean_ticker, clean_market)
                    st.success(f"Analysis triggered for {clean_ticker}! ID: {cid}")
                except Exception as e:
                    st.error(f"Failed to trigger analysis: {e}")

    with list_col:
        st.subheader("Recent analyses")
        
        with Session(engine) as session:
            repo = AnalysisRepository(session)
            running_count = repo.get_running_count()
            analyses = repo.list_recent(limit=20)

            if running_count > 0:
                refresh_col, status_col = st.columns([1, 3])
                with refresh_col:
                    if st.button("Refresh", key="refresh_recent_analyses"):
                        st.rerun()
                with status_col:
                    st.caption(
                        f"{running_count} analysis run(s) pending or running. "
                        "Click Refresh to load the latest status."
                    )

            if not analyses:
                st.info("No analyses found.")
                return

            data = []
            for a in analyses:
                data.append(
                    {
                        "ID": str(a.correlation_id),
                        "Ticker": f"{a.ticker.upper()} ({a.market})",
                        "Status": a.status,
                        "Verdict": a.verdict.upper() if a.verdict else "-",
                        "Date": a.created_at.strftime("%Y-%m-%d %H:%M"),
                    }
                )
            df = pd.DataFrame(data)
            
            # Make sure we maintain a persistent state for the selected row
            # If the dataframe is redrawn, Streamlit resets selection if we don't manage it carefully.
            # Using an empty selection by default is safer for avoiding display bugs if rows shift.
            
            event = st.dataframe(
                df,
                width="stretch",
                hide_index=True,
                on_select="rerun",
                selection_mode="single-row",
                key="analyses_dataframe"
            )
            
            selected_rows = event.selection.rows
            
            # If the user clicked a row, use that index.
            # If nothing is selected, we simply don't display the detailed view at the bottom.
            if selected_rows:
                selected_idx = selected_rows[0]
            
                # Display details for the selected index
                if 0 <= selected_idx < len(df):
                    selected_id = UUID(df.iloc[selected_idx]["ID"])
                    
                    detail = repo.get_by_correlation_id(selected_id)
                    if detail:
                        st.markdown("---")
                        st.subheader(f"Analysis for {detail.ticker.upper()}")
                        
                        status_color = {
                            "completed": "green",
                            "failed": "red",
                            "running": "blue",
                            "pending": "gray"
                        }.get(detail.status, "gray")
                        
                        st.markdown(f"**Status:** :{status_color}[{detail.status.upper()}]")
                        
                        if detail.status == "completed":
                            col1, col2 = st.columns(2)
                            with col1:
                                st.metric("Verdict", detail.verdict.upper() if detail.verdict else "N/A")
                            with col2:
                                st.metric("Conviction", f"{detail.conviction} / 5" if detail.conviction else "N/A")
                            
                            st.markdown("### Report")
                            st.markdown(detail.report_md)
                            
                            if detail.payload:
                                with st.expander("Show Traces & Drivers"):
                                    st.json(detail.payload)
                                    
                        elif detail.status == "failed":
                            st.error(detail.error or "Unknown error")
                            
                        elif detail.status in ("pending", "running"):
                            st.info("Analysis is currently running. Please wait...")
            else:
                st.caption("Click a row in the table above to view the analysis details.")


def main() -> None:
    """Render the Streamlit UI entrypoint."""
    st.set_page_config(page_title="Oraculum Operations", layout="wide")
    st.title("Oraculum Operations")

    refresh_tab, analysis_tab = st.tabs(["Refresh", "Analysis"])
    with refresh_tab:
        _render_refresh_tab()
    with analysis_tab:
        _render_analysis_tab()


if __name__ == "__main__":
    main()
