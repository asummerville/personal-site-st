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
import fred_app.db as db
from fred_app.loader import load_series
from fred_app.sidebar import render_global_sidebar
from fred_app.store import AVAILABLE_SERIES
from fred_app.utils.transforms import cagr, snap_to_date


COST_TYPES = ["Labor", "Materials", "Equipment", "Other"]

# Series eligible to serve as escalation indices (anything that's a level series).
ELIGIBLE_TYPES = {"index", "count"}
ELIGIBLE_SERIES = {
    sid: m for sid, m in AVAILABLE_SERIES.items() if m.series_type in ELIGIBLE_TYPES
}

# Per-cost-type default escalator series (used by F9 per-type mode).
DEFAULT_TYPE_INDICES = {
    "Labor": "CES2000000003",
    "Materials": "WPUSI012011",
    "Equipment": "WPU112",
    "Other": "WPU801",
}

# Lookups for per-line-item escalation index column.
TITLE_TO_SID: dict[str, str] = {m.title: sid for sid, m in ELIGIBLE_SERIES.items()}
ELIGIBLE_TITLES: list[str] = sorted(TITLE_TO_SID)
DEFAULT_TYPE_TITLES: dict[str, str] = {
    ct: ELIGIBLE_SERIES[sid].title for ct, sid in DEFAULT_TYPE_INDICES.items()
}

SAMPLE_PROJECT = pd.DataFrame(
    [
        {"Line Item": "Site Prep & Foundation",  "Cost ($)": 250_000.0, "Cost Type": "Materials",
         "Escalation Index": ELIGIBLE_SERIES["WPUSI012011"].title},
        {"Line Item": "Structural Steel",         "Cost ($)": 480_000.0, "Cost Type": "Materials",
         "Escalation Index": ELIGIBLE_SERIES["WPU1017"].title},
        {"Line Item": "Skilled Labor",            "Cost ($)": 620_000.0, "Cost Type": "Labor",
         "Escalation Index": ELIGIBLE_SERIES["CES2000000003"].title},
        {"Line Item": "Crane & Equipment Rental", "Cost ($)": 145_000.0, "Cost Type": "Equipment",
         "Escalation Index": ELIGIBLE_SERIES["WPU112"].title},
        {"Line Item": "Permits & Insurance",      "Cost ($)":  55_000.0, "Cost Type": "Other",
         "Escalation Index": ELIGIBLE_SERIES["WPU801"].title},
    ]
)


# ── Page setup ────────────────────────────────────────────────────────────────

st.title("Project Escalation")
st.caption(
    "Escalate a past project's costs to today's prices using FRED cost indices. "
    "Use **Single Index** for a quick whole-project estimate, or **Custom Index** for cost-type-specific accuracy."
)

render_global_sidebar()  # Date range isn't directly used here but keeps sidebar consistent.
_db_ready = db.ensure_schema() if db.is_available() else False

st.sidebar.divider()
st.sidebar.header("Tips")
st.sidebar.caption(
    "Edit costs directly in the table. Use the (+) row to add line items. "
    "Switch tabs to compare a single-index escalation against a cost-type-aware one — "
    "the project cost breakdown is shared between tabs."
)


# ── Shared project state ──────────────────────────────────────────────────────

if "project" not in st.session_state:
    st.session_state["project"] = SAMPLE_PROJECT.copy()
if "esc_project_name" not in st.session_state:
    st.session_state["esc_project_name"] = "Sample Project"
if "esc_base_date" not in st.session_state:
    st.session_state["esc_base_date"] = date.today() - relativedelta(years=5)


# ── Project inputs (rendered once, shared by both tabs) ───────────────────────

st.markdown("### Project")

# DB project picker — shown inline above name/date so it reads as "open or create"
if _db_ready:
    saved_projs = db.list_projects()
    if saved_projs:
        proj_options = {p["name"]: p["db_id"] for p in saved_projs}
        pk_col, load_col, del_col = st.columns([4, 1, 1])
        chosen_proj_name = pk_col.selectbox(
            "Open saved project",
            options=["— new project —"] + list(proj_options.keys()),
            key="esc_load_proj_select",
        )
        if chosen_proj_name != "— new project —":
            if load_col.button("Open", key="esc_load_proj_btn", use_container_width=True):
                loaded = db.load_project(proj_options[chosen_proj_name])
                if loaded:
                    st.session_state["esc_project_name"] = loaded["name"]
                    st.session_state["esc_base_date"] = date.fromisoformat(loaded["base_date"])
                    st.session_state["project"] = pd.DataFrame(
                        [
                            {
                                "Line Item": r["line_item"],
                                "Cost ($)": float(r["cost"]),
                                "Cost Type": r["cost_type"],
                                "Escalation Index": r.get("escalation_index")
                                    or DEFAULT_TYPE_TITLES.get(r["cost_type"], ELIGIBLE_SERIES["WPU801"].title),
                            }
                            for r in loaded["line_items"]
                        ]
                    )
                    st.session_state["esc_loaded_db_id"] = proj_options[chosen_proj_name]
                    st.rerun()
            if del_col.button("Delete", key="esc_del_proj_btn", use_container_width=True):
                db.delete_project(proj_options[chosen_proj_name])
                if st.session_state.get("esc_loaded_db_id") == proj_options[chosen_proj_name]:
                    st.session_state.pop("esc_loaded_db_id", None)
                st.rerun()

c1, c2 = st.columns([2, 1])
project_name = c1.text_input("Project name", key="esc_project_name")
base_date = c2.date_input(
    "Base cost date",
    key="esc_base_date",
    max_value=date.today(),
    help="The date the original costs were captured (e.g., when the bid was prepared).",
)

st.markdown("**Cost breakdown**")
# Key includes the loaded DB id so a different project gets a fresh render.
_editor_key = f"project_editor_{st.session_state.get('esc_loaded_db_id', 'new')}"
project_df = st.data_editor(
    st.session_state["project"],
    use_container_width=True,
    num_rows="dynamic",
    column_config={
        "Line Item": st.column_config.TextColumn("Line Item", required=True),
        "Cost ($)": st.column_config.NumberColumn(
            "Cost ($)", min_value=0.0, step=1000.0, format="$%.2f"
        ),
        "Cost Type": st.column_config.SelectboxColumn(
            "Cost Type", options=COST_TYPES, required=True, default="Other"
        ),
        "Escalation Index": st.column_config.SelectboxColumn(
            "Escalation Index",
            options=ELIGIBLE_TITLES,
            help="FRED series used to escalate this line item in the 'Line Item' tab.",
        ),
    },
    key=_editor_key,
)

# Auto-fill any missing Escalation Index cells based on Cost Type default.
if "Escalation Index" not in project_df.columns:
    project_df["Escalation Index"] = project_df["Cost Type"].map(DEFAULT_TYPE_TITLES)
else:
    blank = project_df["Escalation Index"].isna()
    if blank.any():
        project_df.loc[blank, "Escalation Index"] = (
            project_df.loc[blank, "Cost Type"].map(DEFAULT_TYPE_TITLES)
        )

st.session_state["project"] = project_df

action_c1, action_c2, _ = st.columns([1, 1, 4])
if action_c1.button("Reset to sample"):
    st.session_state["project"] = SAMPLE_PROJECT.copy()
    st.session_state.pop("esc_loaded_db_id", None)
    st.rerun()

if _db_ready:
    _is_db_project = "esc_loaded_db_id" in st.session_state
    _save_label = "☁ Update in DB" if _is_db_project else "☁ Save to DB"
    if action_c2.button(_save_label, help="Persist this project to Supabase"):
        valid_rows = project_df.dropna(subset=["Line Item", "Cost ($)"])
        line_items = [
            {
                "line_item": r["Line Item"],
                "cost": float(r["Cost ($)"]) if r["Cost ($)"] is not None else 0.0,
                "cost_type": r["Cost Type"] if r["Cost Type"] in COST_TYPES else "Other",
                "escalation_index": r.get("Escalation Index") or DEFAULT_TYPE_TITLES.get(r.get("Cost Type", "Other"), ELIGIBLE_SERIES["WPU801"].title),
            }
            for _, r in valid_rows.iterrows()
        ]
        db_id = db.save_project(
            name=project_name or "Unnamed Project",
            base_date=base_date.isoformat(),
            line_items=line_items,
        )
        if db_id:
            st.session_state["esc_loaded_db_id"] = db_id
            verb = "updated" if _is_db_project else "saved"
            st.success(f'Project "{project_name}" {verb} in database.')
        else:
            st.error("DB save failed — check connection.")

if project_df.empty or project_df["Cost ($)"].fillna(0).sum() == 0:
    st.info("Add at least one line item with a cost to see escalation results.")
    st.stop()

st.divider()


def render_factor_callout(
    sid: str, base_date: date, base_val: float, curr_val: float, curr_date: date
) -> float:
    meta = AVAILABLE_SERIES[sid]
    years = max((curr_date - base_date).days / 365.25, 0.0)
    factor = curr_val / base_val
    pct = (factor - 1.0) * 100.0
    c = cagr(base_val, curr_val, years) if years >= 1.0 else None
    cagr_label = f", CAGR: {c * 100:.2f}%" if c is not None else ""
    st.success(
        f"**{meta.title}** on {base_date}: **{base_val:.4f}** → on {curr_date}: "
        f"**{curr_val:.4f}**  \nFactor: **{factor:.4f}×** "
        f"({pct:+.2f}% over {years:.1f} years{cagr_label})"
    )
    return factor


def render_index_ref_chart(sid: str, df: pd.DataFrame, base_date: date, key: str) -> None:
    meta = AVAILABLE_SERIES[sid]
    mask = df["date"] >= pd.Timestamp(base_date)
    seg = df.loc[mask]
    if seg.empty:
        return
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=seg["date"], y=seg["value"], mode="lines",
            line=dict(width=2, color=color_for_series(sid)),
            name=meta.title,
        )
    )
    base_ts = pd.Timestamp(base_date).isoformat()
    fig.add_shape(
        type="line", x0=base_ts, x1=base_ts, y0=0, y1=1, yref="paper",
        line=dict(dash="dash", color="#95a5a6", width=1),
    )
    fig.add_annotation(
        x=base_ts, y=1, yref="paper", text="Base",
        showarrow=False, yanchor="bottom", font=dict(color="#95a5a6", size=11),
    )
    fig.update_layout(
        height=220, margin=dict(l=0, r=0, t=10, b=0),
        showlegend=False, hovermode="x unified",
        xaxis_title="", yaxis_title=meta.units,
    )
    st.plotly_chart(fig, use_container_width=True, key=key)


def _to_monthly(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame(columns=["date", "value"])
    out = df.set_index("date").sort_index()
    return out["value"].resample("ME").last().to_frame("value").reset_index()


def _build_composite_df(weights: dict[str, float], base_date: date, wide_store) -> pd.DataFrame | None:
    """Rebuild a composite index DataFrame from F7 weights + base_date."""
    normalized = {}
    for sid, _w in weights.items():
        raw = wide_store.get(sid)
        monthly = _to_monthly(raw)
        if monthly.empty:
            continue
        anchor = snap_to_date(monthly, base_date)
        if anchor is None or anchor["value"] == 0:
            continue
        out = monthly.copy()
        out["value"] = (out["value"] / anchor["value"]) * 100.0
        normalized[sid] = out

    if not normalized:
        return None

    aligned = None
    for sid, df in normalized.items():
        s = df.set_index("date")["value"].rename(sid)
        aligned = s if aligned is None else pd.concat([aligned, s], axis=1, join="outer")

    w_arr = pd.Series({sid: weights[sid] for sid in normalized})
    if w_arr.sum() == 0:
        return None

    def _row(row):
        mask = row.notna()
        if not mask.any():
            return float("nan")
        ww = w_arr[mask.index[mask]]
        return float((row[mask] * ww).sum() / ww.sum()) if ww.sum() else float("nan")

    composite = aligned.apply(_row, axis=1).dropna().reset_index()
    composite.columns = ["date", "value"]
    return composite if not composite.empty else None


# ── Tabs ──────────────────────────────────────────────────────────────────────

tab_single, tab_custom, tab_lineitem = st.tabs(["Single Index", "Custom Index", "Line Item"])


# ============ F8 — Single Index ============

with tab_single:
    st.markdown("### Escalation Index")
    eligible_ids = list(ELIGIBLE_SERIES.keys())
    default_idx = eligible_ids.index("WPU801") if "WPU801" in eligible_ids else 0
    chosen_sid = st.selectbox(
        "Escalation index",
        options=eligible_ids,
        index=default_idx,
        format_func=lambda s: f"{AVAILABLE_SERIES[s].title} ({AVAILABLE_SERIES[s].category})",
        key="f8_index",
    )

    store = load_series((chosen_sid,), date(1900, 1, 1), date.today())
    idx_df = store.get(chosen_sid)

    if idx_df is None or idx_df.empty:
        st.error("Selected index returned no data.")
    else:
        base_row = snap_to_date(idx_df, base_date)
        if base_row is None:
            st.error(
                f"No data for **{AVAILABLE_SERIES[chosen_sid].title}** on or before {base_date}. "
                "Pick a more recent base date or choose a different index."
            )
        else:
            curr_row = idx_df.iloc[-1]
            factor = render_factor_callout(
                chosen_sid,
                base_row["date"].date(),
                float(base_row["value"]),
                float(curr_row["value"]),
                curr_row["date"].date(),
            )

            # Results table
            work = project_df.copy()
            work["Original Cost"] = work["Cost ($)"].fillna(0.0).astype(float)
            work["Escalation Factor"] = factor
            work["Escalated Cost"] = work["Original Cost"] * factor
            work["Change ($)"] = work["Escalated Cost"] - work["Original Cost"]
            work["Change (%)"] = (factor - 1.0) * 100.0

            display = work[["Line Item", "Cost Type", "Original Cost", "Escalation Factor", "Escalated Cost", "Change ($)", "Change (%)"]].copy()
            total_orig = display["Original Cost"].sum()
            total_esc = display["Escalated Cost"].sum()
            total_row = pd.DataFrame([{
                "Line Item": "TOTAL",
                "Cost Type": "",
                "Original Cost": total_orig,
                "Escalation Factor": factor,
                "Escalated Cost": total_esc,
                "Change ($)": total_esc - total_orig,
                "Change (%)": (factor - 1.0) * 100.0,
            }])
            display = pd.concat([display, total_row], ignore_index=True)

            st.markdown("### Results")
            st.dataframe(
                display,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Original Cost": st.column_config.NumberColumn(format="$%.2f"),
                    "Escalation Factor": st.column_config.NumberColumn(format="%.4f"),
                    "Escalated Cost": st.column_config.NumberColumn(format="$%.2f"),
                    "Change ($)": st.column_config.NumberColumn(format="$%.2f"),
                    "Change (%)": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )

            m1, m2, m3 = st.columns(3)
            m1.metric("Original Total", f"${total_orig:,.2f}")
            m2.metric("Escalated Total", f"${total_esc:,.2f}")
            m3.metric("Change", f"${total_esc - total_orig:,.2f}", f"{(factor - 1.0) * 100:+.2f}%")

            # Optional pie + reference chart
            show_pie = st.checkbox("Show cost-type breakdown (pie)", value=False, key="f8_pie")
            if show_pie:
                by_type = work.groupby("Cost Type", as_index=False)["Escalated Cost"].sum()
                pie = go.Figure(go.Pie(labels=by_type["Cost Type"], values=by_type["Escalated Cost"], hole=0.4))
                pie.update_layout(height=320, margin=dict(l=0, r=0, t=10, b=0))
                st.plotly_chart(pie, use_container_width=True, key="f8_pie_chart")

            st.markdown("**Index over the escalation period**")
            render_index_ref_chart(chosen_sid, idx_df, base_row["date"].date(), key="f8_ref")

            csv = display.to_csv(index=False).encode("utf-8")
            st.download_button(
                "Download report (CSV)",
                data=csv,
                file_name=f"escalation_{project_name.replace(' ', '_')}_{base_date}.csv",
                mime="text/csv",
                key="f8_dl",
            )

            st.caption(
                "ℹ︎ Escalation based on national-average indices. Regional cost differences are not applied. "
                "Use Location Normalization (v2) for region-specific adjustments."
            )


# ============ F9 — Custom Index ============

with tab_custom:
    saved_indices: dict = st.session_state.get("custom_indices", {})

    mode = st.radio(
        "Index mode",
        ["Use Saved Custom Index", "Assign per Cost Type"],
        horizontal=True,
        key="f9_mode",
    )

    work = project_df.copy()
    work["Original Cost"] = work["Cost ($)"].fillna(0.0).astype(float)

    if mode == "Use Saved Custom Index":
        if not saved_indices:
            st.warning(
                "No saved custom indices yet. Build one in **Analyze → Custom Index Builder** "
                "and save it, then return here. (Per-type assignment is also available below.)"
            )
        else:
            chosen_name = st.selectbox(
                "Saved index",
                options=list(saved_indices.keys()),
                key="f9_saved_name",
            )
            cfg = saved_indices[chosen_name]
            comp_base_date = date.fromisoformat(cfg["base_date"])

            # Pull all component series, then rebuild composite using the index's own base date.
            all_sids = tuple(cfg["weights"].keys())
            comp_store = load_series(all_sids, date(1900, 1, 1), date.today())
            composite_df = _build_composite_df(cfg["weights"], comp_base_date, comp_store)
            if composite_df is None:
                st.error("Could not rebuild the composite (component data unavailable).")
            else:
                comp_base_row = snap_to_date(composite_df, base_date)
                if comp_base_row is None:
                    st.error(
                        f"Composite has no value on or before {base_date}. "
                        f"Composite starts {composite_df['date'].min().date()}."
                    )
                else:
                    comp_curr_row = composite_df.iloc[-1]
                    factor = float(comp_curr_row["value"]) / float(comp_base_row["value"])

                    years = max((comp_curr_row["date"].date() - comp_base_row["date"].date()).days / 365.25, 0.0)
                    c = cagr(float(comp_base_row["value"]), float(comp_curr_row["value"]), years) if years >= 1.0 else None
                    cagr_label = f", CAGR: {c * 100:.2f}%" if c is not None else ""
                    st.success(
                        f"Composite **{chosen_name}** on {comp_base_row['date'].date()}: **{comp_base_row['value']:.4f}** → "
                        f"on {comp_curr_row['date'].date()}: **{comp_curr_row['value']:.4f}**  \n"
                        f"Factor: **{factor:.4f}×** ({(factor - 1.0) * 100:+.2f}% over {years:.1f} years{cagr_label})"
                    )

                    work["Index Used"] = chosen_name
                    work["Escalation Factor"] = factor
                    work["Escalated Cost"] = work["Original Cost"] * factor
                    work["Change ($)"] = work["Escalated Cost"] - work["Original Cost"]
                    work["Change (%)"] = (factor - 1.0) * 100.0

                    # Reference chart for the composite
                    st.markdown("**Composite index over the escalation period**")
                    seg = composite_df[composite_df["date"] >= pd.Timestamp(base_date)]
                    if not seg.empty:
                        fig = go.Figure()
                        fig.add_trace(go.Scatter(
                            x=seg["date"], y=seg["value"], mode="lines",
                            line=dict(width=2.5, color="#ff4b4b"), name=chosen_name,
                        ))
                        base_ts = pd.Timestamp(comp_base_row["date"]).isoformat()
                        fig.add_shape(
                            type="line", x0=base_ts, x1=base_ts, y0=0, y1=1, yref="paper",
                            line=dict(dash="dash", color="#95a5a6", width=1),
                        )
                        fig.update_layout(
                            height=220, margin=dict(l=0, r=0, t=10, b=0),
                            showlegend=False, hovermode="x unified",
                            xaxis_title="", yaxis_title="Composite (Base = 100)",
                        )
                        st.plotly_chart(fig, use_container_width=True, key="f9_comp_ref")

    else:  # Per-cost-type mode
        if "f9_type_map" not in st.session_state:
            st.session_state["f9_type_map"] = DEFAULT_TYPE_INDICES.copy()

        st.markdown("**Index per cost type**")
        type_map = {}
        cols = st.columns(len(COST_TYPES))
        eligible_ids = list(ELIGIBLE_SERIES.keys())
        for i, ctype in enumerate(COST_TYPES):
            current = st.session_state["f9_type_map"].get(ctype, DEFAULT_TYPE_INDICES[ctype])
            default_idx = eligible_ids.index(current) if current in eligible_ids else 0
            sel = cols[i].selectbox(
                ctype,
                options=eligible_ids,
                index=default_idx,
                format_func=lambda s: AVAILABLE_SERIES[s].title,
                key=f"f9_type_{ctype}",
            )
            type_map[ctype] = sel
        st.session_state["f9_type_map"] = type_map

        # Load all unique series
        all_sids = tuple(set(type_map.values()))
        store = load_series(all_sids, date(1900, 1, 1), date.today())

        # Compute factor per cost type
        type_factors: dict[str, float] = {}
        type_notes: list[str] = []
        for ctype, sid in type_map.items():
            df = store.get(sid)
            if df is None or df.empty:
                type_factors[ctype] = float("nan")
                type_notes.append(f"**{ctype}** ({AVAILABLE_SERIES[sid].title}): no data.")
                continue
            br = snap_to_date(df, base_date)
            if br is None:
                type_factors[ctype] = float("nan")
                type_notes.append(
                    f"**{ctype}** ({AVAILABLE_SERIES[sid].title}): no data at or before {base_date}."
                )
                continue
            type_factors[ctype] = float(df.iloc[-1]["value"]) / float(br["value"])

        for note in type_notes:
            st.warning(note)

        work["Index Used"] = work["Cost Type"].map(lambda t: AVAILABLE_SERIES[type_map.get(t, "WPU801")].title)
        work["Escalation Factor"] = work["Cost Type"].map(type_factors)
        work["Escalated Cost"] = work["Original Cost"] * work["Escalation Factor"]
        work["Change ($)"] = work["Escalated Cost"] - work["Original Cost"]
        work["Change (%)"] = (work["Escalation Factor"] - 1.0) * 100.0

        # Per-type subtotals callout
        st.markdown("**Per-cost-type escalation summary**")
        summary_rows = []
        for ctype in COST_TYPES:
            sub = work[work["Cost Type"] == ctype]
            if sub.empty:
                continue
            sub_orig = sub["Original Cost"].sum()
            sub_esc = sub["Escalated Cost"].sum()
            f = type_factors.get(ctype)
            summary_rows.append({
                "Cost Type": ctype,
                "Index": AVAILABLE_SERIES[type_map[ctype]].title,
                "Factor": round(f, 4) if pd.notna(f) else None,
                "Original": sub_orig,
                "Escalated": sub_esc,
            })
        if summary_rows:
            st.dataframe(
                pd.DataFrame(summary_rows),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Original": st.column_config.NumberColumn(format="$%.2f"),
                    "Escalated": st.column_config.NumberColumn(format="$%.2f"),
                    "Factor": st.column_config.NumberColumn(format="%.4f"),
                },
            )

        total_orig_c = work["Original Cost"].sum()
        total_esc_c = work["Escalated Cost"].sum(skipna=True)
        weighted_factor = total_esc_c / total_orig_c if total_orig_c else float("nan")
        st.info(f"**Weighted average escalation:** {weighted_factor:.4f}× ({(weighted_factor - 1.0) * 100:+.2f}%)")

    # ── Common results table (both modes) ─────────────────────────────────────
    if "Escalation Factor" in work.columns:
        display_c = work[[
            "Line Item", "Cost Type", "Index Used", "Original Cost",
            "Escalation Factor", "Escalated Cost", "Change ($)", "Change (%)"
        ]].copy()
        total_orig_c = display_c["Original Cost"].sum()
        total_esc_c = display_c["Escalated Cost"].sum(skipna=True)
        overall_factor = total_esc_c / total_orig_c if total_orig_c else float("nan")
        total_row_c = pd.DataFrame([{
            "Line Item": "TOTAL",
            "Cost Type": "",
            "Index Used": "Weighted",
            "Original Cost": total_orig_c,
            "Escalation Factor": overall_factor,
            "Escalated Cost": total_esc_c,
            "Change ($)": total_esc_c - total_orig_c,
            "Change (%)": (overall_factor - 1.0) * 100.0,
        }])
        display_c = pd.concat([display_c, total_row_c], ignore_index=True)

        st.markdown("### Results")
        st.dataframe(
            display_c,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Original Cost": st.column_config.NumberColumn(format="$%.2f"),
                "Escalation Factor": st.column_config.NumberColumn(format="%.4f"),
                "Escalated Cost": st.column_config.NumberColumn(format="$%.2f"),
                "Change ($)": st.column_config.NumberColumn(format="$%.2f"),
                "Change (%)": st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Original Total", f"${total_orig_c:,.2f}")
        m2.metric("Escalated Total", f"${total_esc_c:,.2f}")
        m3.metric("Change", f"${total_esc_c - total_orig_c:,.2f}", f"{(overall_factor - 1.0) * 100:+.2f}%")

        # ── Single vs Custom side-by-side comparison ──────────────────────────
        st.markdown("### Single Index vs. Custom Index")
        compare_sid = st.selectbox(
            "Compare against single index",
            options=list(ELIGIBLE_SERIES.keys()),
            index=list(ELIGIBLE_SERIES.keys()).index("WPU801") if "WPU801" in ELIGIBLE_SERIES else 0,
            format_func=lambda s: AVAILABLE_SERIES[s].title,
            key="f9_compare",
        )
        cmp_store = load_series((compare_sid,), date(1900, 1, 1), date.today())
        cmp_df = cmp_store.get(compare_sid)
        if cmp_df is not None and not cmp_df.empty:
            br = snap_to_date(cmp_df, base_date)
            if br is not None:
                single_factor = float(cmp_df.iloc[-1]["value"]) / float(br["value"])
                single_total = total_orig_c * single_factor
                cc1, cc2, cc3 = st.columns(3)
                cc1.metric(
                    f"Single ({AVAILABLE_SERIES[compare_sid].title.split(':')[0][:24]})",
                    f"${single_total:,.2f}",
                    f"{(single_factor - 1.0) * 100:+.2f}%",
                )
                cc2.metric("Custom (this tab)", f"${total_esc_c:,.2f}", f"{(overall_factor - 1.0) * 100:+.2f}%")
                cc3.metric("Custom − Single", f"${total_esc_c - single_total:,.2f}")
            else:
                st.caption("Comparison unavailable: comparison index has no data at base date.")

        csv_c = display_c.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download report (CSV)",
            data=csv_c,
            file_name=f"escalation_custom_{project_name.replace(' ', '_')}_{base_date}.csv",
            mime="text/csv",
            key="f9_dl",
        )


# ============ Line Item tab ============

with tab_lineitem:
    st.markdown("### Per-Line-Item Escalation")
    st.caption(
        "Each row uses the index assigned in the **Escalation Index** column above. "
        "Change any row's index in the cost table to override the default."
    )

    work_li = project_df.copy()
    work_li["Original Cost"] = work_li["Cost ($)"].fillna(0.0).astype(float)
    work_li["_sid"] = work_li["Escalation Index"].map(TITLE_TO_SID)

    unknown = work_li.loc[
        work_li["_sid"].isna() & work_li["Escalation Index"].notna(), "Escalation Index"
    ].unique()
    for t in unknown:
        st.warning(f"Unrecognised escalation index '{t}' — row will be skipped.")

    unique_sids_li = tuple(work_li["_sid"].dropna().unique())
    if not unique_sids_li:
        st.info("No valid escalation indices assigned. Edit the Escalation Index column above.")
    else:
        store_li = load_series(unique_sids_li, date(1900, 1, 1), date.today())

        # Compute factor per row — fetch each unique series once (cached), apply per-row.
        escalation_factors: list[float] = []
        for _, row in work_li.iterrows():
            sid = row["_sid"]
            if pd.isna(sid):
                escalation_factors.append(float("nan"))
                continue
            df_idx = store_li.get(sid)
            if df_idx is None or df_idx.empty:
                escalation_factors.append(float("nan"))
                continue
            br = snap_to_date(df_idx, base_date)
            if br is None:
                escalation_factors.append(float("nan"))
                continue
            escalation_factors.append(float(df_idx.iloc[-1]["value"]) / float(br["value"]))

        work_li["Escalation Factor"] = escalation_factors
        work_li["Escalated Cost"] = work_li["Original Cost"] * work_li["Escalation Factor"]
        work_li["Change ($)"] = work_li["Escalated Cost"] - work_li["Original Cost"]
        work_li["Change (%)"] = (work_li["Escalation Factor"] - 1.0) * 100.0

        # Results table
        display_li = work_li[[
            "Line Item", "Cost Type", "Escalation Index",
            "Original Cost", "Escalation Factor", "Escalated Cost", "Change ($)", "Change (%)"
        ]].copy()

        total_orig_li = display_li["Original Cost"].sum()
        total_esc_li  = display_li["Escalated Cost"].sum(skipna=True)
        eff_factor_li = total_esc_li / total_orig_li if total_orig_li else float("nan")

        total_row_li = pd.DataFrame([{
            "Line Item": "TOTAL", "Cost Type": "", "Escalation Index": "Weighted",
            "Original Cost": total_orig_li, "Escalation Factor": eff_factor_li,
            "Escalated Cost": total_esc_li,
            "Change ($)": total_esc_li - total_orig_li,
            "Change (%)": (eff_factor_li - 1.0) * 100.0,
        }])
        display_li = pd.concat([display_li, total_row_li], ignore_index=True)

        st.markdown("### Results")
        st.dataframe(
            display_li,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Original Cost":     st.column_config.NumberColumn(format="$%.2f"),
                "Escalation Factor": st.column_config.NumberColumn(format="%.4f"),
                "Escalated Cost":    st.column_config.NumberColumn(format="$%.2f"),
                "Change ($)":        st.column_config.NumberColumn(format="$%.2f"),
                "Change (%)":        st.column_config.NumberColumn(format="%.2f%%"),
            },
        )

        m1, m2, m3 = st.columns(3)
        m1.metric("Original Total",  f"${total_orig_li:,.2f}")
        m2.metric("Escalated Total", f"${total_esc_li:,.2f}")
        m3.metric("Change", f"${total_esc_li - total_orig_li:,.2f}", f"{(eff_factor_li - 1.0) * 100:+.2f}%")

        # Escalation factor bar chart — one bar per line item, coloured by assigned index.
        chart_data = work_li.dropna(subset=["Escalation Factor"])
        if not chart_data.empty:
            st.markdown("**Escalation factor by line item**")
            unique_indices = chart_data["Escalation Index"].unique()
            color_map = {title: color_for_series(TITLE_TO_SID.get(title, title)) for title in unique_indices}

            fig_li = go.Figure()
            for idx_title in unique_indices:
                subset = chart_data[chart_data["Escalation Index"] == idx_title]
                fig_li.add_trace(go.Bar(
                    x=subset["Line Item"],
                    y=subset["Escalation Factor"],
                    name=idx_title,
                    marker_color=color_map[idx_title],
                    text=[f"{f:.3f}x" for f in subset["Escalation Factor"]],
                    textposition="outside",
                ))
            fig_li.add_hline(y=1.0, line_dash="dash", line_color="#95a5a6", annotation_text="No change")
            fig_li.update_layout(
                barmode="group",
                height=360,
                margin=dict(l=0, r=0, t=10, b=0),
                yaxis_title="Escalation Factor",
                xaxis_title="",
                legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
            )
            st.plotly_chart(fig_li, use_container_width=True, key="fli_bar")

        csv_li = display_li.to_csv(index=False).encode("utf-8")
        st.download_button(
            "Download report (CSV)",
            data=csv_li,
            file_name=f"escalation_lineitem_{project_name.replace(' ', '_')}_{base_date}.csv",
            mime="text/csv",
            key="fli_dl",
        )


# ── Methodology ───────────────────────────────────────────────────────────────

with st.expander("Methodology"):
    st.markdown(
        """
- **Escalation factor** — `factor = index_current / index_base`. Each date snaps to the
  nearest data point on or before it.
- **Line-item escalation** — `escalated = original × factor`. In per-type mode, the factor
  varies by cost type using a different FRED series for each.
- **Composite mode (F9)** — Reuses a saved composite from the Custom Index Builder
  (normalized to 100 at its own base date, month-end resampled), then takes
  `composite_current / composite_base`.
- **Eligible escalators** — Only level-type series (`index`, `count`). Rate, diffusion,
  and currency series are not valid escalators.
- **National vs. regional** — Indices reflect national averages. Apply Location
  Normalization (v2) for region-specific adjustments.
        """
    )
