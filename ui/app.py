"""Streamlit operations console for manual data-refresh commands."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date

import streamlit as st

from common.config import config
from common.requests.base import Request
from application.refresh_request_factory import (
    STATEMENT_TEMPLATES,
    STATEMENT_VARIANTS,
    build_balance_sheet_request,
    build_cash_flow_statement_request,
    build_income_statement_request,
    build_share_price_request,
    build_ticker_request,
)
from application.refresh_service import RefreshService
from infrastructure.kafka_refresh_request_publisher import KafkaRefreshRequestPublisher

logger = logging.getLogger(__name__)

DEFAULT_MARKET = "us"
DEFAULT_PRICE_VARIANT = "daily"
DEFAULT_SAFETY_WINDOW_DAYS = 7


def _run_awaitable(awaitable: Awaitable[None]) -> None:
    """Execute one awaitable in a fresh event loop."""
    asyncio.run(awaitable)


def _trigger_request(request: Request) -> None:
    """Publish one refresh request and render the result in the UI."""
    service = RefreshService(KafkaRefreshRequestPublisher())
    with st.spinner("Publishing request to Kafka..."):
        _run_awaitable(service.trigger(request))
    st.success(
        f"Published `{request.request_type}` to `{config.harvester_request_topic}`."
    )
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
    ticker_tab, share_price_tab, income_tab, balance_tab, cash_flow_tab = st.tabs(
        [
            "Ticker",
            "Share Price",
            "Income Statement",
            "Balance Sheet",
            "Cash Flow",
        ]
    )
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


def main() -> None:
    """Render the Streamlit UI entrypoint."""
    st.set_page_config(page_title="Oraculum Operations", layout="wide")
    st.title("Oraculum Operations")

    refresh_tab, analysis_tab = st.tabs(["Refresh", "Analysis (coming soon)"])
    with refresh_tab:
        _render_refresh_tab()
    with analysis_tab:
        st.info("Analysis output view is not implemented yet.")


if __name__ == "__main__":
    main()
