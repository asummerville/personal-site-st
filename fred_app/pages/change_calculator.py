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


MAX_SERIES = 5


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("Change Calculator")
st.caption(
    "Compute total % change and average annual growth rate (CAGR) "
    "for any series between two dates."
)

global_start, global_end = render_global_sidebar()


# ── Sidebar: series selection ─────────────────────────────────────────────────

st.sidebar.divider()
st.sidebar.header("Series Selection")
st.sidebar.caption(f"Max {MAX_SERIES} series at a time")

selected_ids: list[str] = []
for cat in CATEGORIES:
    cat_series = series_by_category(cat)
    with st.sidebar.expander(cat, expanded=(cat == "Cost Indices")):
        for sid, meta in cat_series.items():
            default = sid == "WPU801"
            if st.checkbox(meta.title, value=default, key=f"calc_{sid}"):
                selected_ids.append(sid)

render_category_legend()

if not selected_ids:
    st.info("Select at least one series from the sidebar.")
    st.stop()

if len(selected_ids) > MAX_SERIES:
    st.warning(f"Too many series selected — keeping the first {MAX_SERIES}.")
    selected_ids = selected_ids[:MAX_SERIES]


# ── Date range controls (page-level, not global) ──────────────────────────────

st.markdown("### Compare a past date to today")
st.caption(
    "We snap to the nearest data point on or before each date. "
    "Use this to estimate how much costs have escalated since a past project or bid."
)

# Pull a wide window so user can pick any historical date
wide_store = load_series(tuple(selected_ids), date(1900, 1, 1), date.today())

# Earliest available across selected series
earliest_dates = []
for sid in selected_ids:
    df = wide_store.get(sid)
    if df is not None and not df.empty:
        earliest_dates.append(df["date"].min().date())
earliest = min(earliest_dates) if earliest_dates else date(1950, 1, 1)

latest_dates = []
for sid in selected_ids:
    df = wide_store.get(sid)
    if df is not None and not df.empty:
        latest_dates.append(df["date"].max().date())
latest = max(latest_dates) if latest_dates else date.today()

ctrl_col1, ctrl_col2 = st.columns(2)
default_start = max(latest - relativedelta(years=5), earliest)
input_start = ctrl_col1.date_input(
    "Start date",
    value=default_start,
    min_value=earliest,
    max_value=latest,
    help="The past date to compare from. The series will snap to the nearest data point on or before this date.",
)
input_end = ctrl_col2.date_input(
    "End date",
    value=latest,
    min_value=earliest,
    max_value=latest,
    help="Default: the latest available data point.",
)

if input_start >= input_end:
    st.error("Start date must be before end date.")
    st.stop()


# ── Calculations ──────────────────────────────────────────────────────────────

def _compounded_rate_change(df: pd.DataFrame, start: date, end: date) -> float | None:
    """For rate-type series (e.g., monthly growth rates as %): compound them."""
    mask = (df["date"] > pd.Timestamp(start)) & (df["date"] <= pd.Timestamp(end))
    rates = df.loc[mask, "value"].dropna()
    if rates.empty:
        return None
    # FRED rate series are typically expressed as percent — divide by 100 to get decimal
    return float((1.0 + rates / 100.0).prod() - 1.0)


rows = []
notices = []  # Date snapping or insufficient-history warnings to surface

for sid in selected_ids:
    df = wide_store.get(sid)
    meta = AVAILABLE_SERIES[sid]
    if df is None or df.empty:
        rows.append({"_sid": sid, "Series": meta.title, "_skip": True, "Note": "No data"})
        continue

    series_min = df["date"].min().date()
    if input_start < series_min:
        notices.append(
            f"**{meta.title}**: start date is before this series' history (first data: {series_min}). "
            "Result uses the earliest available value."
        )

    s = snap_to_date(df, input_start)
    e = snap_to_date(df, input_end)
    if s is None or e is None:
        rows.append({"_sid": sid, "Series": meta.title, "_skip": True, "Note": "Insufficient data"})
        continue

    s_date_actual = s["date"].date()
    e_date_actual = e["date"].date()
    if s_date_actual != input_start:
        notices.append(f"**{meta.title}**: snapped start to {s_date_actual} (no data on {input_start}).")
    if e_date_actual != input_end:
        notices.append(f"**{meta.title}**: snapped end to {e_date_actual} (no data on {input_end}).")

    years = max((e_date_actual - s_date_actual).days / 365.25, 0.0)

    if meta.series_type == "diffusion":
        # Absolute point change only
        rows.append(
            {
                "_sid": sid,
                "Series": meta.title,
                "Start Date": s_date_actual.isoformat(),
                "Start Value": round(float(s["value"]), 4),
                "End Date": e_date_actual.isoformat(),
                "End Value": round(float(e["value"]), 4),
                "Total % Change": None,
                "Point Change": round(float(e["value"] - s["value"]), 4),
                "Years": round(years, 2),
                "CAGR": None,
                "_skip": False,
            }
        )
    elif meta.series_type == "rate":
        # Compound the per-period rates
        cumulative = _compounded_rate_change(df, s_date_actual, e_date_actual)
        c = None
        if cumulative is not None and years >= 1.0:
            # Equivalent CAGR derived from the compounded total
            c = (1.0 + cumulative) ** (1.0 / years) - 1.0
        rows.append(
            {
                "_sid": sid,
                "Series": meta.title,
                "Start Date": s_date_actual.isoformat(),
                "Start Value": round(float(s["value"]), 4),
                "End Date": e_date_actual.isoformat(),
                "End Value": round(float(e["value"]), 4),
                "Total % Change": cumulative,
                "Years": round(years, 2),
                "CAGR": c,
                "_skip": False,
            }
        )
    else:
        total_pct = (float(e["value"]) / float(s["value"])) - 1.0 if s["value"] else None
        c = cagr(float(s["value"]), float(e["value"]), years) if years >= 1.0 else None
        rows.append(
            {
                "_sid": sid,
                "Series": meta.title,
                "Start Date": s_date_actual.isoformat(),
                "Start Value": round(float(s["value"]), 4),
                "End Date": e_date_actual.isoformat(),
                "End Value": round(float(e["value"]), 4),
                "Total % Change": total_pct,
                "Years": round(years, 2),
                "CAGR": c,
                "_skip": False,
            }
        )

# Surface notices once each
if notices:
    for n in sorted(set(notices)):
        st.caption(f"ℹ︎ {n}")


# ── Results table ─────────────────────────────────────────────────────────────

valid = [r for r in rows if not r.get("_skip")]
skipped = [r for r in rows if r.get("_skip")]

if not valid:
    st.warning("No series could be computed for this date range.")
    st.stop()

# Build display table
display_rows = []
for r in valid:
    pct = r.get("Total % Change")
    cagr_v = r.get("CAGR")
    point = r.get("Point Change")
    display_rows.append(
        {
            "Series": r["Series"],
            "Start Date": r["Start Date"],
            "Start Value": r["Start Value"],
            "End Date": r["End Date"],
            "End Value": r["End Value"],
            "Years": r["Years"],
            "Total % Change": f"{pct * 100:.2f}%" if pct is not None else (
                f"Δ {point:+.2f}" if point is not None else "—"
            ),
            "CAGR": f"{cagr_v * 100:.2f}%" if cagr_v is not None else "—",
        }
    )

st.dataframe(pd.DataFrame(display_rows), use_container_width=True, hide_index=True)

if skipped:
    st.caption(
        "Skipped: " + ", ".join(r["Series"] + f" ({r.get('Note', '')})" for r in skipped)
    )


# ── CAGR bar chart ────────────────────────────────────────────────────────────

cagr_rows = [r for r in valid if r.get("CAGR") is not None]
if cagr_rows:
    sorted_rows = sorted(cagr_rows, key=lambda r: r["CAGR"], reverse=True)
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            y=[r["Series"] for r in sorted_rows],
            x=[r["CAGR"] * 100 for r in sorted_rows],
            orientation="h",
            marker=dict(color=[color_for_series(r["_sid"]) for r in sorted_rows]),
            text=[f"{r['CAGR'] * 100:.2f}%" for r in sorted_rows],
            textposition="outside",
            hovertemplate="%{y}<br>CAGR: %{x:.2f}%<extra></extra>",
        )
    )
    fig.update_layout(
        xaxis_title="CAGR (%)",
        margin=dict(l=0, r=40, t=10, b=0),
        height=max(180, 60 * len(sorted_rows) + 60),
        showlegend=False,
        yaxis=dict(autorange="reversed"),
    )
    st.markdown("### Average Annual Change (CAGR)")
    st.plotly_chart(fig, use_container_width=True, key="f6_cagr_bar")
elif valid:
    st.caption("CAGR not shown: less than 1 year between dates, or all series are diffusion-type.")


# ── Headline callout for the top series ───────────────────────────────────────

# Pick the series with the largest absolute total % change (or point change for diffusion)
def _magnitude(r):
    if r.get("Total % Change") is not None:
        return abs(r["Total % Change"])
    if r.get("Point Change") is not None:
        return abs(r["Point Change"])
    return -1


top = max(valid, key=_magnitude)
top_pct = top.get("Total % Change")
top_cagr = top.get("CAGR")
top_years = top["Years"]
direction = "increased" if (top_pct or 0) >= 0 else "decreased"
if top_pct is not None and top_cagr is not None:
    st.success(
        f"**{top['Series']}** has {direction} by **{abs(top_pct) * 100:.2f}%** over "
        f"**{top_years:.1f} years**, averaging **{top_cagr * 100:.2f}%/yr**."
    )
elif top_pct is not None:
    st.success(
        f"**{top['Series']}** has {direction} by **{abs(top_pct) * 100:.2f}%** over "
        f"**{top_years:.1f} years** (CAGR not meaningful for periods under 1 year)."
    )
elif top.get("Point Change") is not None:
    pc = top["Point Change"]
    st.success(
        f"**{top['Series']}** changed by **{pc:+.2f}** points over **{top_years:.1f} years**."
    )


# ── Copy to clipboard + download ──────────────────────────────────────────────

result_df = pd.DataFrame(display_rows)
copy_text = result_df.to_csv(index=False, sep="\t")

with st.expander("Copy / download results"):
    st.code(copy_text, language="text")
    st.caption("Select all and copy from the box above (Streamlit auto-formats it for paste-into-spreadsheet).")
    st.download_button(
        "Download CSV",
        data=result_df.to_csv(index=False).encode("utf-8"),
        file_name=f"change_calculator_{input_start}_{input_end}.csv",
        mime="text/csv",
    )


# ── Methodology ───────────────────────────────────────────────────────────────

with st.expander("Methodology"):
    st.markdown(
        """
- **Date snapping** — If a date has no data, we use the latest data point on or before it.
- **Total % Change** — `(end_value / start_value) − 1` for index/count series.
- **CAGR** — `(end_value / start_value)^(1 / years) − 1`. Suppressed if the period is under 1 year.
- **Diffusion series** — Show absolute point change instead of % change. CAGR not applicable.
- **Rate series (e.g., monthly growth rates)** — Total change is computed by compounding the per-period rates:
  `Π(1 + rate_t / 100) − 1`. CAGR is derived from that compounded total.
        """
    )
