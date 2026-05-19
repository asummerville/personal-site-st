import sys
import os
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
import streamlit as st

from fred_app.components.charts import (
    dual_axis_chart,
    single_series_chart,
    sparkline,
)
from fred_app.loader import load_series
from fred_app.sidebar import render_category_legend, render_global_sidebar
from fred_app.store import AVAILABLE_SERIES
from fred_app.utils.transforms import time_block_changes, yoy_change


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("Trend: Single Series")
st.caption("Explore a single FRED series — raw values, YoY change, or backward-looking time blocks.")

start_date, end_date = render_global_sidebar()

st.sidebar.divider()
st.sidebar.header("Series Selection")
default_sid = "WPU801"
series_id = st.sidebar.selectbox(
    "Series",
    options=list(AVAILABLE_SERIES.keys()),
    index=list(AVAILABLE_SERIES.keys()).index(default_sid),
    format_func=lambda sid: f"{AVAILABLE_SERIES[sid].title} ({sid})",
    key="single_series_id",
)

render_category_legend()


# ── Load data ─────────────────────────────────────────────────────────────────

store = load_series((series_id,), start_date, end_date)
df = store.get(series_id)
meta = AVAILABLE_SERIES[series_id]

if df is None or df.empty:
    st.warning("No data available for this series in the selected range. Try widening the date range.")
    st.stop()

st.markdown(
    f"**{meta.title}** · `{meta.series_id}` · "
    f"`{meta.frequency}` · `{meta.units}` · `{meta.category}`"
)


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_linear, tab_yoy, tab_blocks = st.tabs(["Linear", "With % Change", "Time Blocks"])


# ── F1 — Linear ───────────────────────────────────────────────────────────────

with tab_linear:
    if len(df) < 3:
        st.warning("Too few data points in this range — try widening the date range.")
    fig = single_series_chart(df, meta.series_id, meta.units)
    st.plotly_chart(fig, use_container_width=True, key="f1_linear")

    summary = store.summary(series_id)
    cols = st.columns(len(summary))
    for col, (label, val) in zip(cols, summary.items()):
        col.metric(label, val)

    with st.expander("Raw data"):
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.download_button(
            "Download CSV",
            data=df.to_csv(index=False).encode("utf-8"),
            file_name=f"{meta.series_id}_{start_date}_{end_date}.csv",
            mime="text/csv",
        )


# ── F2 — Value + YoY % Change ─────────────────────────────────────────────────

with tab_yoy:
    if not meta.yoy_applicable:
        st.info(
            f"**{meta.title}** already expresses a rate of change "
            f"({meta.units}), so a YoY transform is not applied. Showing raw values."
        )
        fig = single_series_chart(df, meta.series_id, meta.units)
        st.plotly_chart(fig, use_container_width=True, key="f2_raw_fallback")
    else:
        ctrl_col1, ctrl_col2 = st.columns([1, 2])
        smoothing = ctrl_col1.selectbox(
            "Smoothing",
            options=["None", "3-period rolling", "12-period rolling"],
            help="Apply a rolling average to the raw value before computing YoY.",
        )
        display_mode = ctrl_col2.radio(
            "Display",
            options=["Both", "Value only", "% Change only"],
            horizontal=True,
        )

        smoothed = df.copy()
        if smoothing == "3-period rolling":
            smoothed["value"] = smoothed["value"].rolling(3).mean()
        elif smoothing == "12-period rolling":
            smoothed["value"] = smoothed["value"].rolling(12).mean()

        with_yoy = yoy_change(smoothed, periods=meta.frequency_periods)

        if with_yoy["yoy"].notna().sum() == 0:
            st.warning(
                "Not enough history for a YoY calculation. "
                f"Need at least {meta.frequency_periods} periods."
            )
        else:
            show_value = display_mode in ("Both", "Value only")
            show_yoy = display_mode in ("Both", "% Change only")
            fig = dual_axis_chart(
                with_yoy,
                series_id=meta.series_id,
                primary_label=meta.units,
                show_value=show_value,
                show_secondary=show_yoy,
            )
            st.plotly_chart(fig, use_container_width=True, key="f2_dual_axis")

            mcol1, mcol2 = st.columns(2)
            with mcol1:
                st.markdown("**Value statistics**")
                v = with_yoy["value"].dropna()
                if not v.empty:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Latest", round(v.iloc[-1], 2))
                    m2.metric("Min", round(v.min(), 2))
                    m3.metric("Max", round(v.max(), 2))
                    m4.metric("Mean", round(v.mean(), 2))
            with mcol2:
                st.markdown("**YoY % change statistics**")
                y = with_yoy["yoy"].dropna()
                if not y.empty:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Latest", f"{y.iloc[-1] * 100:.2f}%")
                    m2.metric("Min", f"{y.min() * 100:.2f}%")
                    m3.metric("Max", f"{y.max() * 100:.2f}%")
                    m4.metric("Mean", f"{y.mean() * 100:.2f}%")


# ── F3 — Time Blocks ──────────────────────────────────────────────────────────

with tab_blocks:
    latest_date = df["date"].max().date()
    ctrl_col1, ctrl_col2 = st.columns([1, 2])
    anchor = ctrl_col1.date_input(
        "Anchor date",
        value=latest_date,
        max_value=latest_date,
        help="Time blocks count backward from this date. Defaults to latest data point.",
    )

    is_diffusion_or_rate = meta.series_type in ("diffusion", "rate")
    default_mode = "Point Change" if is_diffusion_or_rate else "% Change"
    mode_choice = ctrl_col2.radio(
        "Display",
        options=["% Change", "Point Change"],
        index=0 if default_mode == "% Change" else 1,
        horizontal=True,
    )
    mode = "pct" if mode_choice == "% Change" else "point"

    # We need the full series history (not just the visible range) so longer windows work.
    # The current df is already filtered by date range, so re-fetch with a wide range:
    wide_start = date(1900, 1, 1)
    wide_store = load_series((series_id,), wide_start, end_date)
    wide_df = wide_store.get(series_id)
    if wide_df is None or wide_df.empty:
        st.warning("No data available.")
        st.stop()

    table = time_block_changes(wide_df, anchor=anchor, mode=mode)

    display = table.drop(columns=["_insufficient"]).copy()
    if "% Change" in display.columns:
        display["% Change"] = display["% Change"].apply(
            lambda v: f"{v * 100:.2f}%" if pd.notna(v) else "Insufficient data"
        )

    def _fmt(v):
        return "—" if pd.isna(v) else f"{v:.4f}"

    styled = display.style.format(
        {"Start Value": _fmt, "End Value": _fmt, "Change": _fmt},
        na_rep="—",
    )

    change_col = "% Change" if mode == "pct" else "Point Change"
    if change_col in display.columns:
        # Apply red/green to the change cells based on the raw numeric value in table
        raw_change = table[change_col] if change_col in table.columns else table["Change"]

        def _color_cell(v):
            try:
                num = float(v.rstrip("%")) if isinstance(v, str) and v.endswith("%") else float(v)
            except (TypeError, ValueError):
                return ""
            if num > 0:
                return "background-color: rgba(46, 204, 113, 0.25)"
            if num < 0:
                return "background-color: rgba(231, 76, 60, 0.25)"
            return ""

        styled = styled.map(_color_cell, subset=[change_col])

    st.dataframe(styled, use_container_width=True, hide_index=True)

    st.caption("Reference sparkline (full available history)")
    st.plotly_chart(sparkline(wide_df, meta.series_id), use_container_width=True, key="f3_sparkline")

    st.download_button(
        "Download CSV",
        data=display.to_csv(index=False).encode("utf-8"),
        file_name=f"{meta.series_id}_timeblocks_{anchor}.csv",
        mime="text/csv",
    )
