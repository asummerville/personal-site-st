import sys
import os
sys.path.insert(
    0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

from datetime import date
from dateutil.relativedelta import relativedelta
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from fred_app.components.charts import color_for_series
from fred_app.loader import load_series
from fred_app.sidebar import render_category_legend, render_global_sidebar
from fred_app.store import AVAILABLE_SERIES, CATEGORIES, series_by_category
from fred_app.utils.transforms import cagr, snap_to_date


MAX_SERIES = 8


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("Custom Index Builder")
st.caption(
    "Build a weighted composite index from multiple series. "
    "Set weights to reflect a project's cost mix (e.g., 40% materials, 35% labor, 25% equipment)."
)

global_start, global_end = render_global_sidebar()


# ── Sidebar: series selection ─────────────────────────────────────────────────

st.sidebar.divider()
st.sidebar.header("Series Selection")
st.sidebar.caption(f"Max {MAX_SERIES} series in a composite")

selected_ids: list[str] = []
for cat in CATEGORIES:
    cat_series = series_by_category(cat)
    expanded = cat in ("Cost Indices", "Materials")
    with st.sidebar.expander(cat, expanded=expanded):
        for sid, meta in cat_series.items():
            default = sid in ("WPU801", "WPUSI012011", "CES2000000003")
            if st.checkbox(meta.title, value=default, key=f"cib_{sid}"):
                selected_ids.append(sid)

render_category_legend()

if not selected_ids:
    st.info("Select at least one series from the sidebar.")
    st.stop()

if len(selected_ids) > MAX_SERIES:
    st.warning(f"Too many series selected — keeping the first {MAX_SERIES}.")
    selected_ids = selected_ids[:MAX_SERIES]

# Filter out series_types that don't make sense as composite components
incompatible = [
    sid for sid in selected_ids
    if AVAILABLE_SERIES[sid].series_type in ("diffusion", "rate")
]
if incompatible:
    names = ", ".join(AVAILABLE_SERIES[s].title for s in incompatible)
    st.warning(
        f"Excluded from composite (rate/diffusion series can't be index-normalized): {names}"
    )
    selected_ids = [s for s in selected_ids if s not in incompatible]

if not selected_ids:
    st.info("Pick at least one index, count, or currency-type series.")
    st.stop()


# ── Load data ─────────────────────────────────────────────────────────────────

store = load_series(tuple(selected_ids), global_start, global_end)

earliest_dates = []
latest_dates = []
for sid in selected_ids:
    df = store.get(sid)
    if df is not None and not df.empty:
        earliest_dates.append(df["date"].min().date())
        latest_dates.append(df["date"].max().date())

if not earliest_dates:
    st.warning("No data loaded for the selected series and date range.")
    st.stop()

# Common window where all selected series have data
common_start = max(earliest_dates)
common_end = min(latest_dates)
if common_start >= common_end:
    st.warning("Selected series do not share an overlapping date range. Widen the global range or change series.")
    st.stop()


# ── Weights panel ─────────────────────────────────────────────────────────────

st.markdown("### Weights")
st.caption("Set each series' contribution. Composite is the weighted average of normalized values.")

# Session-state-backed weight defaults
for sid in selected_ids:
    wkey = f"cib_w_{sid}"
    if wkey not in st.session_state:
        st.session_state[wkey] = round(100.0 / len(selected_ids), 2)

# Quick action buttons
b1, b2, b3 = st.columns(3)
if b1.button("Distribute equally", use_container_width=True):
    equal = round(100.0 / len(selected_ids), 2)
    for sid in selected_ids:
        st.session_state[f"cib_w_{sid}"] = equal
    st.rerun()
if b2.button("Normalize to 100", use_container_width=True):
    total = sum(float(st.session_state.get(f"cib_w_{s}", 0.0)) for s in selected_ids)
    if total > 0:
        for sid in selected_ids:
            st.session_state[f"cib_w_{sid}"] = round(
                float(st.session_state[f"cib_w_{sid}"]) * 100.0 / total, 2
            )
        st.rerun()
if b3.button("Zero all", use_container_width=True):
    for sid in selected_ids:
        st.session_state[f"cib_w_{sid}"] = 0.0
    st.rerun()

weights: dict[str, float] = {}
for sid in selected_ids:
    meta = AVAILABLE_SERIES[sid]
    col1, col2 = st.columns([3, 1])
    col1.markdown(f"**{meta.title}**  \n<small style='color:#777'>{meta.category} · {meta.frequency}</small>", unsafe_allow_html=True)
    w = col2.number_input(
        "Weight",
        min_value=0.0,
        max_value=100.0,
        step=1.0,
        key=f"cib_w_{sid}",
        label_visibility="collapsed",
    )
    weights[sid] = float(w)

total_weight = sum(weights.values())
if abs(total_weight - 100.0) < 0.01:
    st.success(f"Total weight: **{total_weight:.2f} / 100** ✓")
elif total_weight == 0:
    st.error("Total weight is 0 — assign weights to at least one series.")
    st.stop()
else:
    st.warning(
        f"Total weight: **{total_weight:.2f} / 100** — composite will rescale proportionally. "
        "Use 'Normalize to 100' to lock it in."
    )


# ── Base date control ─────────────────────────────────────────────────────────

st.markdown("### Base Date")
st.caption("All selected series are rebased to 100 at this date before weighting.")

default_base = max(common_end - relativedelta(years=5), common_start)
base_date = st.date_input(
    "Normalization base date",
    value=default_base,
    min_value=common_start,
    max_value=common_end,
    help="The composite and all components equal 100 at this date.",
)


# ── Build composite ───────────────────────────────────────────────────────────

# Resample each series to month-end frequency so we can weight them on a common grid.
def _to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value"])
    out = df.set_index("date").sort_index()
    out = out["value"].resample("ME").last().to_frame("value").reset_index()
    return out


normalized: dict[str, pd.DataFrame] = {}
anchors: dict[str, float] = {}
for sid in selected_ids:
    raw = store.get(sid)
    monthly = _to_monthly(raw)
    if monthly.empty:
        continue
    anchor = snap_to_date(monthly, base_date)
    if anchor is None or anchor["value"] == 0:
        st.warning(f"Skipping {AVAILABLE_SERIES[sid].title}: no value at or before base date.")
        continue
    anchors[sid] = float(anchor["value"])
    out = monthly.copy()
    out["value"] = (out["value"] / anchor["value"]) * 100.0
    normalized[sid] = out

if not normalized:
    st.warning("No series could be normalized at the chosen base date.")
    st.stop()

# Align all normalized series on a shared date grid (inner join), then weighted-average.
aligned = None
for sid, df in normalized.items():
    s = df.set_index("date")["value"].rename(sid)
    aligned = s if aligned is None else pd.concat([aligned, s], axis=1, join="outer")

# Weighted average row-wise; if a series is NaN on a row, redistribute weight among present series.
weights_arr = pd.Series({sid: weights[sid] for sid in normalized})
if weights_arr.sum() == 0:
    st.error("All contributing series have zero weight.")
    st.stop()


def _weighted_row(row: pd.Series) -> float:
    mask = row.notna()
    if not mask.any():
        return float("nan")
    w = weights_arr[mask.index[mask]]
    if w.sum() == 0:
        return float("nan")
    return float((row[mask] * w).sum() / w.sum())


composite = aligned.apply(_weighted_row, axis=1)
composite_df = composite.dropna().reset_index()
composite_df.columns = ["date", "value"]

if composite_df.empty:
    st.warning("Composite has no valid points. Try widening the date range or changing the base date.")
    st.stop()


# ── Composite chart ───────────────────────────────────────────────────────────

st.markdown("### Composite Index")

fig = go.Figure()

# Components (light)
for sid, df in normalized.items():
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["value"],
            name=AVAILABLE_SERIES[sid].title,
            mode="lines",
            line=dict(width=1, color=color_for_series(sid)),
            opacity=0.45,
            connectgaps=False,
        )
    )

# Composite (bold)
fig.add_trace(
    go.Scatter(
        x=composite_df["date"],
        y=composite_df["value"],
        name="Composite",
        mode="lines",
        line=dict(width=3, color="#ff4b4b"),
    )
)

# Base date marker
ts = pd.Timestamp(base_date).isoformat()
fig.add_shape(
    type="line",
    x0=ts, x1=ts, y0=0, y1=1, yref="paper",
    line=dict(dash="dash", color="#95a5a6", width=1),
)
fig.add_annotation(
    x=ts, y=1, yref="paper",
    text=f"Base = 100 ({base_date})", showarrow=False, yanchor="bottom",
    font=dict(color="#95a5a6", size=11),
)

fig.update_layout(
    xaxis_title="Date",
    yaxis_title=f"Index (Base = 100)",
    margin=dict(l=0, r=0, t=10, b=0),
    height=450,
    hovermode="x unified",
    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
)
st.plotly_chart(fig, use_container_width=True, key="f7_composite")


# ── Component breakdown table ─────────────────────────────────────────────────

st.markdown("### Component Breakdown")

end_composite = composite_df["value"].iloc[-1]
years_total = (composite_df["date"].iloc[-1] - composite_df["date"].iloc[0]).days / 365.25

rows = []
for sid in selected_ids:
    if sid not in normalized:
        continue
    df = normalized[sid]
    meta = AVAILABLE_SERIES[sid]
    last = df["value"].iloc[-1]
    years = (df["date"].iloc[-1] - df["date"].iloc[0]).days / 365.25
    indiv_cagr = cagr(100.0, float(last), years) if years >= 1.0 else None
    # Weighted contribution = (weight / total_weight) * (last_norm - 100)
    eff_weight = weights[sid] / total_weight if total_weight else 0
    contribution = eff_weight * (float(last) - 100.0)
    rows.append({
        "Series": meta.title,
        "Weight": f"{weights[sid]:.2f}",
        "Effective %": f"{eff_weight * 100:.2f}%",
        "Latest (Norm)": round(float(last), 2),
        "Individual CAGR": f"{indiv_cagr * 100:.2f}%" if indiv_cagr is not None else "—",
        "Weighted Contribution": round(contribution, 2),
    })

composite_cagr = cagr(100.0, float(end_composite), years_total) if years_total >= 1.0 else None

st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

c1, c2, c3 = st.columns(3)
c1.metric("Composite Latest", f"{end_composite:.2f}")
c2.metric("Change since base", f"{end_composite - 100:+.2f} pts")
c3.metric(
    "Composite CAGR",
    f"{composite_cagr * 100:.2f}%" if composite_cagr is not None else "—",
)


# ── Save / Load custom indices ────────────────────────────────────────────────

st.divider()
st.markdown("### Save This Index")
st.caption("Saved indices persist in this session and will be available in Project Escalation pages.")

if "custom_indices" not in st.session_state:
    st.session_state["custom_indices"] = {}

save_col, name_col = st.columns([1, 3])
default_name = st.session_state.get("cib_last_name", "My Composite")
index_name = name_col.text_input("Index name", value=default_name, key="cib_name_input")
can_save = abs(total_weight - 100.0) < 0.01

if save_col.button("Save Index", type="primary", disabled=not can_save, use_container_width=True):
    st.session_state["custom_indices"][index_name] = {
        "name": index_name,
        "weights": {sid: weights[sid] for sid in selected_ids if sid in normalized},
        "base_date": base_date.isoformat(),
        "series_ids": list(normalized.keys()),
    }
    st.session_state["cib_last_name"] = index_name
    st.success(f"Saved “{index_name}”.")

if not can_save:
    st.caption("Save is disabled until weights sum to 100. Use 'Normalize to 100' above.")

if st.session_state["custom_indices"]:
    st.markdown("**Saved indices**")
    for name, cfg in list(st.session_state["custom_indices"].items()):
        r1, r2, r3 = st.columns([3, 4, 1])
        r1.markdown(f"**{name}**")
        weight_summary = ", ".join(
            f"{AVAILABLE_SERIES[s].title.split(':')[0][:18]} {w:.0f}%"
            for s, w in cfg["weights"].items()
        )
        r2.caption(f"Base {cfg['base_date']} · {weight_summary}")
        if r3.button("✕", key=f"cib_del_{name}"):
            del st.session_state["custom_indices"][name]
            st.rerun()


# ── Download composite ────────────────────────────────────────────────────────

with st.expander("Download composite data"):
    csv = composite_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Download Composite CSV",
        data=csv,
        file_name=f"composite_{index_name.replace(' ', '_')}_{base_date}.csv",
        mime="text/csv",
    )


# ── Methodology ───────────────────────────────────────────────────────────────

with st.expander("Methodology"):
    st.markdown(
        """
- **Normalization** — Each component is rebased so that the value at the base date equals 100:
  `norm_i(t) = (v_i(t) / v_i(base_date)) * 100`.
- **Frequency alignment** — All components are resampled to month-end (last observation in month) so
  mixed-frequency series (monthly, quarterly, daily) can be combined on a common grid.
- **Composite** — Weighted average of normalized components:
  `composite(t) = Σ(w_i · norm_i(t)) / Σ(w_i)`.
- **Missing data** — If a component has no value for a given date, its weight is temporarily
  redistributed across the remaining components for that date.
- **Weighted contribution** — `(w_i / Σw) × (norm_i_latest − 100)`. Sums to roughly the composite's
  change since base; minor differences come from missing-data redistribution.
- **Excluded series types** — Rate and diffusion series can't be index-normalized and are filtered out.
        """
    )
