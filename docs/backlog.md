# Construction Cost Explorer — Bug Inventory & Improvement Backlog

**Review date:** 2026-05-19
**Scope:** Full codebase review following the Supabase persistence + per-line-item escalation session. Covers all files under `fred_app/`.

---

## Bugs

### High

**`fred_app/db.py` — `_init_schema` caches a failed initialization silently**
`_init_schema` is decorated with `@st.cache_resource`, so its result is cached for the life of the process. If schema initialization raises an exception, `st.warning()` fires once and the function returns `False`. Every subsequent call across all pages returns the cached `False` with no error — a broken DB is indistinguishable from a degraded-but-alive one. Fix: let the exception propagate (remove the try/except or re-raise), or at minimum log the error every time `ensure_schema()` is called and finds a cached `False`.

**`fred_app/db.py` — `list_custom_indices()` and `list_projects()` swallow all exceptions**
Both functions have bare `except Exception: return []`. A broken DB connection, a schema mismatch, or a Supabase outage all silently return empty lists — the UI looks identical to "no saved data exists." Fix: add `st.warning("Could not load saved data: {e}")` (or equivalent logging) in each except block so failures are visible to the user.

---

### Medium

**`fred_app/pages/trend_single.py:196–199` — `_row_color` is dead code**
`_row_color` is defined but never applied to the styled DataFrame. The `_insufficient` column is dropped from `display` before the styler is created, so even if `.apply(_row_color, axis=1)` were added it would error. Remove the function and the `_insufficient` drop to eliminate confusion.

**`fred_app/pages/trend_single.py:207–210` — Stats table shows unformatted floats**
`styled.format({"Start Value": _format_value, "End Value": _format_value, "Change": _format_value})` uses `_format_value`, which returns the raw Python value for non-NaN inputs (no formatting). The table renders values like `123.4567` instead of `123.46`. Fix: replace with `lambda v: "—" if pd.isna(v) else f"{v:.2f}"`.

**`fred_app/pages/project_escalation.py` — "Reset to sample" leaves stale editor widget state**
The reset handler clears `esc_loaded_db_id` and assigns `st.session_state["project"] = SAMPLE_PROJECT.copy()`, but does not clear `st.session_state["project_editor_new"]`. If a user had previously edited a new project, those edits persist in widget state and the data_editor renders them over the sample data. Fix: add `st.session_state.pop("project_editor_new", None)` in the reset handler.

**`fred_app/store.py` — `DTWEXBGS` (Trade Weighted USD Index) has wrong `series_type`**
`DTWEXBGS` is in category `"Currency"` but `series_type="index"`, which makes it eligible as a project escalation index. Escalating a project cost by a currency-basket index is almost never the right behavior. Fix: set `series_type="currency"` to exclude it from escalation options, consistent with how other currency series are handled. If keeping `"index"`, add a `notes` field documenting the deliberate choice.

---

### Low

**`fred_app/pages/project_escalation.py` — Stale data_editor keys accumulate in session state**
Editor keys like `project_editor_5`, `project_editor_7` are set each time a project is loaded and never cleaned up. Harmless at current scale, but over a long multi-project session state grows unboundedly. Fix: pop the previous editor key in the load/reset handler before assigning a new one.

**`fred_app/sidebar.py:29` — `st.stop()` inside shared utility is a fragile convention**
`render_global_sidebar()` calls `st.stop()` when `start_date >= end_date`, halting the entire page render. This is correct as a guard but requires all pages to call `render_global_sidebar()` before any widget setup — otherwise those widgets disappear without explanation. All pages currently comply, but the convention is nowhere documented. Add a comment in `sidebar.py` and in `CLAUDE.md`.

**`fred_app/pages/trend_single.py:80–85` — Download button missing `key=`**
The "Download CSV" button inside `with st.expander("Raw data"):` has no explicit `key=`. On Streamlit 1.36+ this auto-generates a key from the label, which is safe as long as no other button on the page shares the same label. Low risk currently; add `key="download_raw_csv"` for explicitness.

**`fred_app/pages/project_escalation.py` — Negative costs accepted silently**
The data_editor accepts negative `Cost ($)` values (no `min_value` on the `NumberColumn`). A negative cost produces a negative escalated cost with no warning. Fix: add `min_value=0.0` to the `NumberColumn` config or add a post-edit validation check with `st.warning`.

---

## Improvements

| Item | Files | Effort | Value | Notes |
|---|---|---|---|---|
| **Extract `_to_monthly` and composite-build logic into `transforms.py`** | `pages/custom_index_builder.py`, `pages/project_escalation.py`, `utils/transforms.py` | M | 4/5 | `_to_monthly(df)` is copy-pasted identically in both files. The normalization loop in `_build_composite_df` (project_escalation) also duplicates the composite-building logic in `custom_index_builder`. Move both to `transforms.py` and import from there. |
| **DB upsert for custom indices by ID** | `fred_app/db.py`, `pages/custom_index_builder.py` | S | 4/5 | `save_custom_index()` uses name-based lookup; renaming a saved index in a future session creates a duplicate row. Apply the same fix used for `save_project`: accept an optional `db_id` param and use `UPDATE` when present. |
| **Document why full-history `load_series` calls bypass the global date filter** | `pages/project_escalation.py`, `pages/change_calculator.py`, `pages/trend_single.py` | S | 3/5 | Several pages call `load_series` with `date(1900,1,1)` / `date.today()` regardless of sidebar dates. This is intentional (`snap_to_date` needs full history for arbitrary base dates) but looks like a bug to a future reader. Add a one-line comment at each call site. |
| **Validate composite series IDs against `AVAILABLE_SERIES` before fetching** | `pages/project_escalation.py` | S | 3/5 | In `_build_composite_df`, weights keys are passed to `store.get(sid)` without checking existence. If a saved custom index in the DB references a series_id removed from `AVAILABLE_SERIES`, it silently contributes no data. Emit a `st.warning` per missing series. |
| **`render_global_sidebar()` return-value convention is mixed** | `fred_app/sidebar.py`, all `pages/*.py` | S | 2/5 | The function returns `(start_date, end_date)` but most pages ignore the return value and read from session state directly. Pick one canonical pattern: either return nothing and document that callers use `st.session_state`, or make the return value the canonical API and update all pages. |
| **Consider `series_type="level"` or reclassify `CES2000000003`** | `fred_app/store.py` | S | 2/5 | "Construction: Average Hourly Earnings" uses `series_type="count"`, which is functionally correct (it's a level series) but semantically misleading — hourly earnings is not a count. `"index"` is also arguable since it normalizes well. Low priority; at minimum add a `notes` field explaining the choice. |
| **Increase `load_series` TTL or make it configurable** | `fred_app/loader.py` | S | 2/5 | The 1-hour `@st.cache_data(ttl=3600)` TTL causes unnecessary FRED API calls for series that update monthly or quarterly. A 24-hour TTL (`ttl=86400`) would suffice for most series. Consider reading from an env var (`FRED_CACHE_TTL`) so it can be shortened in development. |
| **Remove `fetch_series_info()` dead code from `client.py`** | `fred_app/client.py` | S | 1/5 | `fetch_series_info()` at line 35–37 is defined but never called anywhere. Remove it to reduce surface area, or promote it to actual use if series metadata is ever needed at runtime. |
