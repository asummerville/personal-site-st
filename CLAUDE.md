# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

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

| `series_type` | YoY transform | Time-block default | Multi-axis default |
|---|---|---|---|
| `index` | applied | % Change | Primary axis (rebased) |
| `count` | applied | % Change | Secondary axis (raw) |
| `rate` | skipped (raw view) | Point Change | Secondary axis (raw) |
| `diffusion` | skipped | Point Change | Secondary axis (raw, baseline-50 line shown) |
| `currency` | skipped | % Change | Secondary axis (raw) |

### Streamlit Cloud deployment

Both apps are deployed via Streamlit Cloud pointing at this repo. The `fred_app/app.py` entry point and every page file under `fred_app/pages/` use `sys.path.insert` to add the repo root so that `from fred_app.xxx import ...` resolves regardless of Streamlit's working directory.

## Reference Documents

- `ui-spec.md` — Full UI/UX spec for all 11 planned features (F1–F11). Source of truth for behavior, inputs, outputs, and transforms.
