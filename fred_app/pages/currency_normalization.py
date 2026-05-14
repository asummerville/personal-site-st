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
from fred_app.sidebar import render_global_sidebar
from fred_app.store import AVAILABLE_SERIES
from fred_app.utils.transforms import snap_to_date


# ── Currency registry ─────────────────────────────────────────────────────────
# Maps currency code → (FRED series ID, convention, display name).
# Convention "usd_per": rate quotes USD per 1 unit of foreign  → USD = foreign × rate
# Convention "per_usd": rate quotes foreign per 1 USD          → USD = foreign / rate
CURRENCIES: dict[str, dict] = {
    "USD": {"series": None, "convention": None, "name": "US Dollar"},
    "EUR": {"series": "DEXUSEU", "convention": "usd_per", "name": "Euro"},
    "GBP": {"series": "DEXUSUK", "convention": "usd_per", "name": "British Pound"},
    "AUD": {"series": "DEXUSAL", "convention": "usd_per", "name": "Australian Dollar"},
    "CAD": {"series": "DEXCAUS", "convention": "per_usd", "name": "Canadian Dollar"},
    "JPY": {"series": "DEXJPUS", "convention": "per_usd", "name": "Japanese Yen"},
    "BRL": {"series": "DEXBZUS", "convention": "per_usd", "name": "Brazilian Real"},
}


def to_usd(amount: float, ccy: str, rate: float) -> float:
    """Convert `amount` in `ccy` to USD using the rate, respecting the currency's quote convention."""
    if ccy == "USD":
        return amount
    if CURRENCIES[ccy]["convention"] == "usd_per":
        return amount * rate
    return amount / rate


def from_usd(amount_usd: float, ccy: str, rate: float) -> float:
    """Convert USD `amount_usd` into `ccy` using the rate."""
    if ccy == "USD":
        return amount_usd
    if CURRENCIES[ccy]["convention"] == "usd_per":
        return amount_usd / rate
    return amount_usd * rate


def convert(amount: float, source: str, target: str, rate_source: float | None, rate_target: float | None) -> float | None:
    """Convert source→target via USD pivot. Returns None if a needed rate is missing."""
    if source == target:
        return amount
    # source → USD
    if source == "USD":
        usd = amount
    else:
        if rate_source is None:
            return None
        usd = to_usd(amount, source, rate_source)
    # USD → target
    if target == "USD":
        return usd
    if rate_target is None:
        return None
    return from_usd(usd, target, rate_target)


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("Currency Normalization")
st.caption(
    "Convert a project cost from a foreign currency to USD (or vice versa) at the historical "
    "exchange rate, so escalation can be applied in consistent USD terms."
)

st.info(
    "**Workflow order:** Currency Normalization → Location Normalization → Escalation. "
    "The USD-normalized cost feeds into Project Escalation as the original cost."
)

render_global_sidebar()  # Keep sidebar consistent across pages.


# ── Inputs ────────────────────────────────────────────────────────────────────

# Defaults
if "fx_source" not in st.session_state:
    st.session_state["fx_source"] = "EUR"
if "fx_target" not in st.session_state:
    st.session_state["fx_target"] = "USD"
if "fx_amount" not in st.session_state:
    st.session_state["fx_amount"] = 1_000_000.0
if "fx_date" not in st.session_state:
    st.session_state["fx_date"] = date.today() - relativedelta(years=2)

ccy_list = list(CURRENCIES.keys())

c1, c2, c3 = st.columns([1, 1, 1])
source = c1.selectbox(
    "Source currency",
    options=ccy_list,
    format_func=lambda c: f"{c} — {CURRENCIES[c]['name']}",
    key="fx_source",
)
target = c2.selectbox(
    "Target currency",
    options=ccy_list,
    format_func=lambda c: f"{c} — {CURRENCIES[c]['name']}",
    key="fx_target",
)
if c3.button("⇄ Swap currencies", use_container_width=True):
    st.session_state["fx_source"], st.session_state["fx_target"] = (
        st.session_state["fx_target"],
        st.session_state["fx_source"],
    )
    st.rerun()

c4, c5 = st.columns([1, 1])
amount = c4.number_input(
    f"Amount ({source})",
    min_value=0.0,
    step=10_000.0,
    format="%.2f",
    key="fx_amount",
)
conversion_date = c5.date_input(
    "Conversion date",
    max_value=date.today(),
    key="fx_date",
)

if source == target:
    st.warning("Source and target are the same — no conversion needed.")
    st.stop()

data_source = st.radio(
    "Rate source",
    ["FRED bilateral rate", "Manual entry"],
    horizontal=True,
    key="fx_data_source",
)

manual_rate = None
if data_source == "Manual entry":
    # Show the appropriate direction label so the user knows what they're entering.
    if source == "USD":
        rate_label = f"Rate ({CURRENCIES[target]['name']} per 1 USD)"
    elif target == "USD":
        if CURRENCIES[source]["convention"] == "usd_per":
            rate_label = f"Rate (USD per 1 {source})"
        else:
            rate_label = f"Rate ({source} per 1 USD)"
    else:
        rate_label = f"Rate ({source} ↔ {target})"
    manual_rate = st.number_input(rate_label, min_value=0.0, step=0.01, format="%.6f", value=1.0)


# ── Look up rates from FRED ───────────────────────────────────────────────────

def _lookup_rate(ccy: str) -> tuple[float | None, date | None, pd.DataFrame | None]:
    """Return (rate, snapped_date, full_df) for a currency on or before the conversion date."""
    if ccy == "USD":
        return None, None, None
    sid = CURRENCIES[ccy]["series"]
    store = load_series((sid,), date(1900, 1, 1), date.today())
    df = store.get(sid)
    if df is None or df.empty:
        return None, None, None
    row = snap_to_date(df, conversion_date)
    if row is None:
        return None, None, df
    return float(row["value"]), row["date"].date(), df


rate_src, snapped_src, df_src = _lookup_rate(source)
rate_tgt, snapped_tgt, df_tgt = _lookup_rate(target)

# If manual override, apply it on the appropriate leg
if data_source == "Manual entry" and manual_rate is not None:
    if source != "USD" and target == "USD":
        rate_src = manual_rate
        snapped_src = conversion_date
    elif target != "USD" and source == "USD":
        rate_tgt = manual_rate
        snapped_tgt = conversion_date
    # cross-pair manual entry: treat manual_rate as direct source→target multiplier
    elif source != "USD" and target != "USD":
        converted_direct = amount * manual_rate
        st.success(
            f"**{amount:,.2f} {source}** on {conversion_date} → "
            f"**{converted_direct:,.2f} {target}** at manual rate **{manual_rate:.6f}**"
        )
        st.caption("Cross-currency manual entry uses the rate as a direct source→target multiplier.")
        st.stop()

# Surface snapping notices
if source != "USD" and snapped_src and snapped_src != conversion_date:
    st.caption(f"ℹ︎ {source} rate snapped to {snapped_src} (no quote on {conversion_date}, common for weekends/holidays).")
if target != "USD" and snapped_tgt and snapped_tgt != conversion_date:
    st.caption(f"ℹ︎ {target} rate snapped to {snapped_tgt}.")

converted = convert(amount, source, target, rate_src, rate_tgt)

if converted is None:
    missing = source if (source != "USD" and rate_src is None) else target
    st.error(
        f"No FX data for **{missing}** on or before {conversion_date}. "
        "Try a later date or switch to manual entry."
    )
    st.stop()


# ── Result ────────────────────────────────────────────────────────────────────

st.markdown("### Conversion Result")

# Show the effective end-to-end rate (target per 1 source)
effective_rate = converted / amount if amount else float("nan")
st.success(
    f"**{amount:,.2f} {source}** on {conversion_date} → "
    f"**{converted:,.2f} {target}**  \n"
    f"Effective rate: **1 {source} = {effective_rate:.6f} {target}**"
)

# Quick comparison: today's rate for context
rate_src_today, _, _ = (None, None, None) if source == "USD" else (float(df_src.iloc[-1]["value"]), df_src.iloc[-1]["date"].date(), df_src) if df_src is not None and not df_src.empty else (None, None, None)
rate_tgt_today, _, _ = (None, None, None) if target == "USD" else (float(df_tgt.iloc[-1]["value"]), df_tgt.iloc[-1]["date"].date(), df_tgt) if df_tgt is not None and not df_tgt.empty else (None, None, None)
if data_source == "FRED bilateral rate":
    today_converted = convert(amount, source, target, rate_src_today, rate_tgt_today)
    if today_converted is not None and amount:
        delta_pct = (today_converted / converted - 1.0) * 100.0
        m1, m2, m3 = st.columns(3)
        m1.metric(f"At {conversion_date}", f"{converted:,.2f} {target}")
        m2.metric("At today's rate", f"{today_converted:,.2f} {target}", f"{delta_pct:+.2f}%")
        m3.metric("Difference", f"{today_converted - converted:,.2f} {target}")


# ── FX rate chart ±2 years ────────────────────────────────────────────────────

st.markdown("### Exchange Rate History")

# Pick the most relevant chart: the non-USD currency's FRED bilateral series.
chart_ccy = source if source != "USD" else target
chart_df = df_src if source != "USD" else df_tgt
if chart_df is not None and not chart_df.empty and data_source == "FRED bilateral rate":
    sid = CURRENCIES[chart_ccy]["series"]
    meta = AVAILABLE_SERIES[sid]
    window_start = conversion_date - relativedelta(years=2)
    window_end = min(date.today(), conversion_date + relativedelta(years=2))
    mask = (chart_df["date"] >= pd.Timestamp(window_start)) & (chart_df["date"] <= pd.Timestamp(window_end))
    seg = chart_df.loc[mask]

    fig = go.Figure()
    if not seg.empty:
        fig.add_trace(
            go.Scatter(
                x=seg["date"], y=seg["value"], mode="lines",
                line=dict(width=2, color=color_for_series(sid)),
                name=meta.title,
            )
        )
        ts = pd.Timestamp(conversion_date).isoformat()
        fig.add_shape(
            type="line", x0=ts, x1=ts, y0=0, y1=1, yref="paper",
            line=dict(dash="dash", color="#ff4b4b", width=1.5),
        )
        fig.add_annotation(
            x=ts, y=1, yref="paper", text="Conversion date",
            showarrow=False, yanchor="bottom", font=dict(color="#ff4b4b", size=11),
        )
    fig.update_layout(
        height=300,
        margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False,
        hovermode="x unified",
        xaxis_title="",
        yaxis_title=meta.units,
    )
    st.plotly_chart(fig, use_container_width=True, key="f10_fx_chart")
    st.caption(meta.notes)
elif data_source == "Manual entry":
    st.caption("Chart unavailable in manual-entry mode.")


# ── Apply to project (USD only) ───────────────────────────────────────────────

st.divider()
st.markdown("### Apply to Project")

if target != "USD":
    st.caption(
        "ℹ︎ To feed this into Project Escalation (which works in USD), set **Target currency** to USD."
    )
else:
    apply = st.toggle(
        "Apply this conversion to the Project Escalation page",
        value=False,
        key="fx_apply_toggle",
    )
    if apply:
        st.session_state["currency_adjustment"] = {
            "source_currency": source,
            "source_amount": float(amount),
            "conversion_date": conversion_date.isoformat(),
            "rate": effective_rate,
            "usd_amount": float(converted),
        }
        st.success(
            f"Applied. **${converted:,.2f} USD** is now the normalized project cost. "
            "Open **Escalate → Project Escalation** to use it as the project total."
        )
        st.caption(
            "Note: the Project Escalation page does not yet auto-populate from this adjustment. "
            "For now, manually enter the USD amount above as your project's original cost."
        )
    else:
        st.session_state.pop("currency_adjustment", None)


# ── Methodology ───────────────────────────────────────────────────────────────

with st.expander("Methodology & FRED conventions"):
    st.markdown(
        """
- **FRED bilateral rate** — Daily exchange rate from the H.10 release. Weekend/holiday gaps
  are snapped to the most recent prior business day.
- **Quote conventions** (differ per pair — direction matters!):
  - `DEXUSEU`, `DEXUSUK`, `DEXUSAL` — USD per 1 unit of foreign → `USD = foreign × rate`.
  - `DEXCAUS`, `DEXJPUS`, `DEXBZUS` — foreign units per 1 USD → `USD = foreign / rate`.
- **Cross-currency conversion** — Source → USD → Target via the USD pivot. Effective rate
  shown is `converted_amount / source_amount`.
- **Manual entry** — Used as a direct rate; for cross-currency manual rates, it's applied
  as a single `source × rate = target` multiplier.
- **Today's rate comparison** — Shows the same nominal amount at the latest FRED quote so
  you can see how much the currency has moved.
        """
    )
