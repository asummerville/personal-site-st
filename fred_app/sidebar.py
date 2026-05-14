from datetime import date
from dateutil.relativedelta import relativedelta
import streamlit as st

from fred_app.store import AVAILABLE_SERIES, CATEGORIES


def render_global_sidebar() -> tuple[date, date]:
    """Render the date range picker that's shared across all pages.

    Series selection is left to each page since pages have different needs
    (single-select, multi-select, grouped, etc.). Returns the (start, end) dates.
    """
    today = date.today()
    default_start = today - relativedelta(years=10)

    if "date_start" not in st.session_state:
        st.session_state["date_start"] = default_start
    if "date_end" not in st.session_state:
        st.session_state["date_end"] = today

    st.sidebar.header("Global Filters")
    col1, col2 = st.sidebar.columns(2)
    start_date = col1.date_input("Start", key="date_start")
    end_date = col2.date_input("End", key="date_end")

    if start_date >= end_date:
        st.sidebar.error("Start must be before end.")
        st.stop()

    if st.sidebar.button("Reset Filters", use_container_width=True):
        for k in ("date_start", "date_end"):
            st.session_state.pop(k, None)
        st.rerun()

    return start_date, end_date


def render_category_legend() -> None:
    """Render a compact summary of available categories and series counts."""
    st.sidebar.divider()
    st.sidebar.caption("Available series")
    for cat in CATEGORIES:
        count = sum(1 for m in AVAILABLE_SERIES.values() if m.category == cat)
        st.sidebar.caption(f"• {cat} — {count}")
