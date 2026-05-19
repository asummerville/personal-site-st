# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## `onenote_to_notion/` — OneNote → Notion Migration

Standalone script that parses OneNote `.mht` exports and pushes content to Notion via the API.

### Usage

1. Export from OneNote desktop: **File → Export → Notebook → Single File Web Page (`.mht`)**
   - Exports the whole notebook as one `.mht` (flat: all pages under one Notion parent)
   - OR export section-by-section to a folder (each filename → a Notion section sub-page)

2. Edit the config block at the top of `onenote_to_notion/migrate.py`:
   ```python
   INPUT          = "path/to/MyNotebook.mht"   # file or folder of .mht files
   NOTION_TOKEN   = "ntn_..."                  # from notion.so/my-integrations
   PARENT_PAGE_ID = "32-char-page-id"          # from the target Notion page URL
   DRY_RUN        = True                       # flip to False for the real run
   ```

3. Run:
   ```bash
   pip install -r onenote_to_notion/requirements.txt
   python onenote_to_notion/migrate.py
   ```

### What it handles
- Bullet lists (including OneNote's non-standard sibling-`<ul>` nesting)
- Numbered lists
- Paragraphs and bold section labels (→ `heading_3`)
- Nested bullets preserved as Notion children blocks
- Notion API rate limiting and 100-block-per-request batching
- Image-only pages (screenshots) produce empty Notion pages gracefully

### Known limitations
- Section names are not embedded in notebook-level `.mht` exports — use per-section exports if hierarchy matters
- Images/screenshots are not migrated (text-only)

## Running the Apps

```bash
# Personal site
streamlit run app/main.py

# Construction Cost Explorer (multi-page)
streamlit run fred_app/app.py
```

Both apps require Python 3.10+ and Streamlit 1.36+ (for `st.navigation`). Install dependencies with:
```bash
pip install -r requirements.txt
```

The construction cost app requires a `.env` file in the repo root:
```
FRED_API_KEY=<your_key>
```
On Streamlit Cloud, set this as a secret (`FRED_API_KEY`) in the app settings instead.

## Architecture

This repo contains two independent Streamlit apps:

**`app/main.py`** — A personal portfolio site. Static content; images in `app/img/`.

**`fred_app/`** — A multi-page construction cost data explorer using `st.navigation`. Pulls from the FRED API. Spec for all 11 planned features lives in `ui-spec.md` at the repo root.

### `fred_app/` package layout

| Module | Responsibility |
|---|---|
| `app.py` | Entry point. Sets `st.set_page_config`, declares pages via `st.Page` / `st.navigation`. |
| `client.py` | `FredClient` — thin `fredapi` wrapper. Fetches a series ID and returns a tidy `[date, value]` DataFrame. |
| `store.py` | `SeriesMeta` dataclass + `AVAILABLE_SERIES` registry + `DataStore`. Each series has metadata (`series_type`, `base_year`, `frequency_periods`, `yoy_applicable`) that gates downstream behavior. |
| `loader.py` | `load_series(ids, start, end) → DataStore`, wrapped in `@st.cache_data` (1-hour TTL). Per-series fetch errors are surfaced as `st.warning` so partial results still render. |
| `sidebar.py` | `render_global_sidebar()` — shared date range picker. Pages add their own series selection on top. |
| `utils/transforms.py` | Pure-function math: `snap_to_date`, `yoy_change`, `normalize_to_base`, `total_pct_change`, `cagr`, `time_block_changes`. |
| `components/charts.py` | Plotly chart builders. `color_for_series(sid)` returns a deterministic color so the same series gets the same color across every page. |
| `pages/` | One file per page. Each must add the repo root to `sys.path` before importing `fred_app.*` (Streamlit Cloud runs pages with the entry script's directory as cwd). |

### Adding a new FRED series

Add an entry to `AVAILABLE_SERIES` in `fred_app/store.py`. Required fields: `series_id`, `title`, `units`, `frequency`, `category`. Optional but recommended: `series_type` (`"index"` / `"rate"` / `"count"` / `"diffusion"` / `"currency"`), `base_year`, `frequency_periods` (12 monthly / 4 quarterly / 1 annual / 252 daily), `yoy_applicable`. The series appears automatically in any page that iterates `AVAILABLE_SERIES`.

### Adding a new page

1. Create `fred_app/pages/<name>.py`. Begin with the `sys.path.insert` shim.
2. Import `render_global_sidebar` from `fred_app.sidebar` so the date range stays consistent.
3. Use `load_series(...)` from `fred_app.loader` for cached fetches.
4. Use chart builders from `fred_app.components.charts` and math from `fred_app.utils.transforms`.
5. Register it in the `PAGES` dict in `fred_app/app.py`.

### Series type → behavior table

| `series_type` | YoY transform | Time-block default | Multi-axis default | Change Calculator | Custom Index Builder |
|---|---|---|---|---|---|
| `index` | applied | % Change | Primary axis (rebased) | Total % change + CAGR | Included (normalized) |
| `count` | applied | % Change | Secondary axis (raw) | Total % change + CAGR | Included (normalized) |
| `rate` | skipped (raw view) | Point Change | Secondary axis (raw) | Mean rate + point change (pp); CAGR suppressed | **Excluded** |
| `diffusion` | skipped | Point Change | Secondary axis (raw, baseline-50 line shown) | Point change only; CAGR suppressed | **Excluded** |
| `currency` | skipped | % Change | Secondary axis (raw) | Total % change + CAGR | Included (normalized) |

**Rate series note (Change Calculator):** FRED rate series (e.g., CPALTT01USM661S) store already-expressed annual percent values (~3.2 = 3.2% YoY). Compounding them as monthly multipliers is wrong. The calculator shows mean rate over the period and start→end point change in percentage points instead.

### Streamlit Cloud deployment

Both apps are deployed via Streamlit Cloud pointing at this repo. The `fred_app/app.py` entry point and every page file under `fred_app/pages/` use `sys.path.insert` to add the repo root so that `from fred_app.xxx import ...` resolves regardless of Streamlit's working directory.

### Session state contracts (cross-page data)

| Key | Written by | Read by | Shape |
|---|---|---|---|
| `custom_indices` | F7 Custom Index Builder | F8/F9 Project Escalation | `dict[name, {name, weights: dict[sid, float], base_date: str, series_ids: list[str], db_id?: int}]` |
| `currency_adjustment` | F10 Currency Normalization | F8/F9 Project Escalation (future) | `{source_currency, source_amount, conversion_date: str, rate, usd_amount}` |
| `date_start` / `date_end` | `render_global_sidebar()` | all pages | `date` |
| `project` | F8/F9 Project Escalation | F8/F9 (shared across tabs) | `pd.DataFrame` with columns: Line Item, Cost ($), Cost Type, Escalation Index |
| `esc_project_name` | F8/F9 Project Escalation | F8/F9 | `str` — project name text input key |
| `esc_base_date` | F8/F9 Project Escalation | F8/F9 | `date` — base cost date input key |
| `esc_loaded_db_id` | F8/F9 Project Escalation (on DB load/save) | F8/F9 | `int` — DB id of the currently loaded project; absent for new/unsaved |
| `cib_db_loaded` | F7 Custom Index Builder | F7 | `bool` flag — DB indices already merged into session on this run |
| `f9_type_map` | F9 Custom Index tab | F9 | `dict[cost_type, series_id]` — per-type index selections |

### Implemented pages

| Feature | File | Status |
|---|---|---|
| F1–F3 | `pages/trend_single.py` | Done |
| F4–F5 | `pages/trend_multi.py` | Done |
| F6 | `pages/change_calculator.py` | Done |
| F7 | `pages/custom_index_builder.py` | Done |
| F8–F9 | `pages/project_escalation.py` | Done |
| F10 | `pages/currency_normalization.py` | Done |
| F11 | — | Deferred to v2 (needs location factor dataset) |

**All F1–F10 are complete. F11 is the only remaining feature.**

### Known Streamlit gotchas (learned in this project)

- **Tabs share a single render pass** — Streamlit executes all `with tab_X:` blocks every run. **Never call `st.stop()` inside a `with tab_X:` block** — it halts the entire render pass and all subsequent tab content blocks never execute. Use `if/else` guards instead. `st.stop()` is only safe at the top level of a page (before `st.tabs()`).
- **Widget key + value conflict** — When a widget uses `key=`, initialize the session state key first (`if "key" not in st.session_state: st.session_state["key"] = default`), then use `key=` only — do not also pass `value=`/`index=`.
- **`st.data_editor` key must be dynamic when data changes** — If you load new data into `st.session_state["project"]` and call `st.rerun()`, the editor ignores it when the key is the same (it keeps its internal edit-delta state). Make the key include a discriminator (e.g., the loaded project's DB id) so a different project forces a fresh widget render. Also clear `st.session_state.pop(editor_key, None)` explicitly before the rerun to discard stale edit deltas.
- **`st.toast` icon must be an emoji** — `icon="✓"` raises `StreamlitAPIException`. Use emoji characters like `icon="✅"`.
- **Plotly chart key required** — Every `st.plotly_chart` call needs a unique `key=` argument (Streamlit 1.36+).
- **`add_vline` crashes with `pd.Timestamp` axes in Plotly 6.x** — Use `add_shape(type="line", x0=ts, x1=ts, y0=0, y1=1, yref="paper")` + `add_annotation` instead.
- **Dark mode** — Never use `color="#111"` or `color="#fff"` for chart lines. Use `#ff4b4b` (Streamlit accent) for bold/composite lines — visible in both themes.
- **`applymap` removed in pandas 3.0** — Use `.map()` on Styler objects instead.
- **`st.cache_resource` caches exceptions silently** — If a `@st.cache_resource` function calls `st.warning()` inside an `except` block and returns a default, subsequent calls return the cached default without re-running the warning. Don't rely on `st.warning` inside cached functions for ongoing error visibility.

### Currency series conventions (F10)

`currency_normalization.py` defines a `CURRENCIES` dict with `convention` field:
- `"usd_per"` → rate = USD per 1 foreign unit → `USD = foreign × rate` (EUR, GBP, AUD)
- `"per_usd"` → rate = foreign per 1 USD → `USD = foreign / rate` (CAD, JPY, BRL)

To add a new currency: add an entry to `CURRENCIES` in that file and add the FRED series to `AVAILABLE_SERIES` in `store.py` with `series_type="currency"`, `frequency_periods=252` (daily), `yoy_applicable=False`, and document the direction in `notes`.

### Project Escalation (F8/F9/Line Item)

Project inputs (name, base date, cost breakdown) are rendered **above** `st.tabs()` to avoid `StreamlitDuplicateElementKey`. All three tabs read from the same `project_df`, `base_date`, `project_name` variables. Eligible escalators are `series_type ∈ {"index", "count"}` only — rate/diffusion/currency series are excluded.

The cost table (`st.data_editor`) has four columns: Line Item, Cost ($), Cost Type, Escalation Index. The Escalation Index column is a `SelectboxColumn` storing FRED series titles (not IDs). A `TITLE_TO_SID` reverse-lookup dict maps titles → IDs at compute time. Auto-fill applies cost-type defaults to blank Escalation Index cells after each data_editor render.

**data_editor key pattern** — The editor key is `f"project_editor_{st.session_state.get('esc_loaded_db_id', 'new')}"`. This forces a fresh widget render when a different project is loaded. The widget state for that key is explicitly cleared (`.pop()`) on both "Open" (load from DB) and after "Save/Update" to prevent stale edit deltas from shadowing freshly loaded DB values.

**DB save/update pattern** — `db.save_project()` accepts an optional `project_id` kwarg. When `esc_loaded_db_id` is set, the save passes it for a direct `UPDATE WHERE id = %s` (bypasses name lookup, prevents duplicate rows on rename or whitespace mismatch).

### DB layer (`fred_app/db.py`)

Optional Supabase/PostgreSQL persistence. `CONNECTION_STRING` env var (Supabase transaction pooler URL). App degrades gracefully to session-state-only if absent.

- `is_available()` — returns `bool(CONNECTION_STRING)`. Gate all DB calls behind this.
- `ensure_schema()` — call once at top of any DB-using page. Runs `CREATE TABLE IF NOT EXISTS` + migrations via `@st.cache_resource` (once per process).
- All CRUD functions catch exceptions and return empty/None on failure — never propagate to the page.
- Tables: `custom_indices`, `projects`, `project_line_items` (with `escalation_index TEXT` column added via migration).

## Reference Documents

- `ui-spec.md` — Full UI/UX spec for all 11 planned features (F1–F11). Source of truth for behavior, inputs, outputs, and transforms.
- `docs/roadmap.md` — 4-sprint, 8-week plan: URL persistence → materials drill-down → forecasting → reporting + FX wiring.
- `docs/feature-backlog.md` — Prioritized ideas beyond the 8-week window (effort S/M/L, portfolio/domain value 1–5).
- `docs/data-sources.md` — Tier 1–5 free public data sources; FRED series IDs for Sprint 2 materials sub-indices.
- `docs/database-schema.md` — Supabase schema + RLS policies + migration plan (design complete; migration deferred).
- `docs/ux-vision.md` — Persona, 5 design principles, navigation evolution horizons, anti-patterns.
- `docs/backlog.md` — Code review findings: confirmed bugs (with file:line + fix) and improvement backlog (effort/value table). Updated 2026-05-19.
