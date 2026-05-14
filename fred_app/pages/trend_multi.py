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
    color_for_series,
    mixed_axis_chart,
    multi_series_chart,
)
from fred_app.loader import load_series
from fred_app.sidebar import render_category_legend, render_global_sidebar
from fred_app.store import AVAILABLE_SERIES, CATEGORIES, series_by_category
from fred_app.utils.transforms import cagr, normalize_to_base, snap_to_date


MAX_SERIES = 8


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("Trend: Multi-Series")
st.caption("Compare multiple FRED series on one chart. Rebase to a common index, or mix axes.")

start_date, end_date = render_global_sidebar()


# ── Sidebar: series selection by category ─────────────────────────────────────

st.sidebar.divider()
st.sidebar.header("Series Selection")
st.sidebar.caption(f"Max {MAX_SERIES} series at a time")

selected_ids: list[str] = []
for cat in CATEGORIES:
    cat_series = series_by_category(cat)
    with st.sidebar.expander(cat, expanded=(cat == "Cost Indices")):
        for sid, meta in cat_series.items():
            default = sid in ("WPU801", "WPUSI012011")
            if st.checkbox(meta.title, value=default, key=f"multi_{sid}"):
                selected_ids.append(sid)

render_category_legend()

if not selected_ids:
    st.info("Select at least 2 series from the sidebar to compare.")
    st.stop()

if len(selected_ids) == 1:
    st.info("Only 1 series selected — multi-series comparison needs at least 2. Add another series from the sidebar.")
    st.stop()

if len(selected_ids) > MAX_SERIES:
    st.warning(f"Too many series selected — showing the first {MAX_SERIES}. Deselect some to add others.")
    selected_ids = selected_ids[:MAX_SERIES]


# ── Load data ─────────────────────────────────────────────────────────────────

store = load_series(tuple(selected_ids), start_date, end_date)

available_ids = [sid for sid in selected_ids if store.get(sid) is not None and not store.get(sid).empty]
if not available_ids:
    st.warning("No data available for the selected series in this date range.")
    st.stop()

# Warn on mixed frequencies
freqs = {AVAILABLE_SERIES[sid].frequency for sid in available_ids}
if len(freqs) > 1:
    st.caption(f"⚠ Mixed frequencies: {', '.join(sorted(freqs))}. Each series renders at its native frequency.")


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_norm, tab_mixed = st.tabs(["Normalized", "Mixed Axis"])


# ── F4 — Normalized ───────────────────────────────────────────────────────────

with tab_norm:
    default_base = (end_date - relativedelta(years=10))
    earliest_dates = []
    for sid in available_ids:
        df = store.get(sid)
        if df is not None and not df.empty:
            earliest_dates.append(df["date"].min().date())
    earliest_overall = max(earliest_dates) if earliest_dates else default_base

    ctrl_col1, ctrl_col2 = st.columns([1, 1])
    base_date = ctrl_col1.date_input(
        "Index base date",
        value=max(default_base, earliest_overall),
        min_value=earliest_overall,
        max_value=end_date,
        help="All series are rebased to this date = 100.",
    )
    base_value = ctrl_col2.number_input(
        "Base value", value=100.0, step=10.0, min_value=1.0,
    )

    normalized: dict[str, pd.DataFrame] = {}
    titles = {sid: AVAILABLE_SERIES[sid].title for sid in available_ids}

    for sid in available_ids:
        df = store.get(sid)
        norm = normalize_to_base(df, base_date, base_value)
        normalized[sid] = norm

    fig = multi_series_chart(
        normalized,
        titles=titles,
        y_label=f"Index (Base {base_date} = {base_value:.0f})",
        base_date=base_date,
    )
    st.plotly_chart(fig, use_container_width=True, key="f4_normalized")

    # Summary table
    rows = []
    for sid in available_ids:
        meta = AVAILABLE_SERIES[sid]
        norm = normalized[sid]
        clean = norm.dropna(subset=["value"])
        if clean.empty:
            continue
        latest = clean.iloc[-1]
        change_since_base = latest["value"] - base_value
        years = max((latest["date"].date() - base_date).days / 365.25, 0.001)
        c = cagr(base_value, latest["value"], years)
        rows.append(
            {
                "Series": f"{meta.title}",
                "Category": meta.category,
                "Latest Normalized": round(float(latest["value"]), 2),
                "Change Since Base": round(float(change_since_base), 2),
                "Avg Annual % Change": f"{c * 100:.2f}%" if c is not None else "—",
            }
        )
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    with st.expander("Methodology"):
        st.markdown(
            f"- Each series is rebased so that its value on **{base_date}** "
            f"(or the nearest prior data point) equals **{base_value:.0f}**.\n"
            "- `normalized(t) = value(t) / value(base_date) × base_value`\n"
            "- Gaps in source data are rendered as breaks, not interpolated."
        )


# ── F5 — Mixed Axis ───────────────────────────────────────────────────────────

with tab_mixed:
    st.caption(
        "Use this view to combine rebasable indices (left axis) with diffusion / rate / count series (right axis)."
    )

    # Auto-assign by series_type
    auto_primary = [
        sid for sid in available_ids
        if AVAILABLE_SERIES[sid].series_type == "index"
    ]
    auto_secondary = [
        sid for sid in available_ids
        if AVAILABLE_SERIES[sid].series_type != "index"
    ]

    ctrl_col1, ctrl_col2 = st.columns(2)
    primary_ids = ctrl_col1.multiselect(
        "Primary axis (will be rebased)",
        options=available_ids,
        default=auto_primary,
        format_func=lambda sid: AVAILABLE_SERIES[sid].title,
    )
    secondary_ids = ctrl_col2.multiselect(
        "Secondary axis (raw values)",
        options=available_ids,
        default=auto_secondary,
        format_func=lambda sid: AVAILABLE_SERIES[sid].title,
    )

    overlap = set(primary_ids) & set(secondary_ids)
    if overlap:
        st.warning(f"Series can only appear on one axis. Removing duplicates from secondary: {', '.join(overlap)}")
        secondary_ids = [s for s in secondary_ids if s not in overlap]

    base_col1, base_col2 = st.columns(2)
    earliest_primary = []
    for sid in primary_ids:
        df = store.get(sid)
        if df is not None and not df.empty:
            earliest_primary.append(df["date"].min().date())
    base_min = max(earliest_primary) if earliest_primary else (end_date - relativedelta(years=10))
    default_mixed_base = max(end_date - relativedelta(years=10), base_min)

    mixed_base_date = base_col1.date_input(
        "Index base date (primary axis)",
        value=default_mixed_base,
        min_value=base_min,
        max_value=end_date,
        key="mixed_base_date",
    )
    secondary_label = base_col2.text_input(
        "Secondary axis label",
        value="Raw value (native units)",
    )

    primary_dfs: dict[str, pd.DataFrame] = {}
    for sid in primary_ids:
        df = store.get(sid)
        if df is None or df.empty:
            continue
        primary_dfs[sid] = normalize_to_base(df, mixed_base_date, 100.0)

    secondary_dfs: dict[str, pd.DataFrame] = {}
    for sid in secondary_ids:
        df = store.get(sid)
        if df is None or df.empty:
            continue
        secondary_dfs[sid] = df

    if not primary_dfs and not secondary_dfs:
        st.info("Assign at least one series to either axis.")
    else:
        # Show baseline-50 line only if any diffusion series on secondary
        has_diffusion = any(
            AVAILABLE_SERIES[sid].series_type == "diffusion" for sid in secondary_ids
        )
        titles = {sid: AVAILABLE_SERIES[sid].title for sid in (primary_ids + secondary_ids)}
        fig = mixed_axis_chart(
            primary_dfs=primary_dfs,
            secondary_dfs=secondary_dfs,
            titles=titles,
            primary_label=f"Index (Base {mixed_base_date} = 100)",
            secondary_label=secondary_label,
            base_date=mixed_base_date,
            show_50_line=has_diffusion,
        )
        st.plotly_chart(fig, use_container_width=True, key="f5_mixed_axis")

        # Mini legend table
        legend_rows = []
        for sid in primary_ids:
            legend_rows.append(
                {"Series": AVAILABLE_SERIES[sid].title, "Axis": "Primary (rebased)", "Color": color_for_series(sid)}
            )
        for sid in secondary_ids:
            legend_rows.append(
                {"Series": AVAILABLE_SERIES[sid].title, "Axis": "Secondary (raw, dashed)", "Color": color_for_series(sid)}
            )
        if legend_rows:
            st.dataframe(
                pd.DataFrame(legend_rows).drop(columns=["Color"]),
                use_container_width=True,
                hide_index=True,
            )
