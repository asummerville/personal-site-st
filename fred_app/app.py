from datetime import date
import streamlit as st
import plotly.graph_objects as go
import pandas as pd

from fred_app.client import FredClient
from fred_app.store import DataStore, AVAILABLE_SERIES


st.set_page_config(page_title="FRED Economic Data", layout="wide")
st.title("FRED Economic Data Explorer")
st.caption("Data sourced from the Federal Reserve Bank of St. Louis (FRED).")


# ── Sidebar controls ──────────────────────────────────────────────────────────

st.sidebar.header("Controls")

selected_ids = st.sidebar.multiselect(
    "Series",
    options=list(AVAILABLE_SERIES.keys()),
    default=["UNRATE", "FEDFUNDS"],
    format_func=lambda sid: f"{sid} — {AVAILABLE_SERIES[sid].title}",
)

col1, col2 = st.sidebar.columns(2)
start_date = col1.date_input("Start", value=date(2000, 1, 1))
end_date = col2.date_input("End", value=date.today())

if start_date >= end_date:
    st.sidebar.error("Start date must be before end date.")
    st.stop()

if not selected_ids:
    st.info("Select at least one series from the sidebar.")
    st.stop()


# ── Data fetching (cached per unique combination of inputs) ───────────────────

@st.cache_data(ttl=3600, show_spinner="Fetching data from FRED…")
def load_data(series_ids: tuple[str, ...], start: date, end: date) -> DataStore:
    client = FredClient()
    store = DataStore()
    for sid in series_ids:
        df = client.fetch_series(sid, start=start, end=end)
        store.add(sid, df, AVAILABLE_SERIES[sid])
    return store


store = load_data(tuple(selected_ids), start_date, end_date)


# ── Charts ────────────────────────────────────────────────────────────────────

for sid in selected_ids:
    df = store.get(sid)
    meta = store.meta[sid]

    if df is None or df.empty:
        st.warning(f"No data returned for {sid}.")
        continue

    st.subheader(f"{meta.title} ({sid})")
    st.caption(f"{meta.frequency} · {meta.units}")

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["value"],
            mode="lines",
            name=sid,
            line=dict(width=2),
        )
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=meta.units,
        margin=dict(l=0, r=0, t=10, b=0),
        height=350,
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)

    summary = store.summary(sid)
    if summary:
        cols = st.columns(len(summary))
        for col, (label, val) in zip(cols, summary.items()):
            col.metric(label, val)

    st.divider()
