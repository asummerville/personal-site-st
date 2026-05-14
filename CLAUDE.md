# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Running the Apps

```bash
# Personal site
streamlit run app/main.py

# FRED economic data explorer
streamlit run fred_app/app.py
```

Both apps require Python 3.10+. Install dependencies with:
```bash
pip install -r requirements.txt
```

The FRED app requires a `.env` file in the repo root:
```
FRED_API_KEY=<your_key>
```
On Streamlit Cloud, set this as a secret (`FRED_API_KEY`) in the app settings instead.

## Architecture

This repo contains two independent Streamlit apps:

**`app/main.py`** — A personal portfolio site. Static content with a sidebar headshot/bio and a main column of project/skills/interests copy. Images live in `app/img/`.

**`fred_app/`** — A FRED economic data visualization app, structured as a Python package:
- `client.py` — `FredClient` wraps the `fredapi` library. Fetches a series by ID and returns a clean `DataFrame` with `[date, value]` columns and a datetime index.
- `store.py` — `DataStore` (dataclass) holds fetched DataFrames keyed by series ID alongside `SeriesMeta` objects. `AVAILABLE_SERIES` is the registry of series the app knows about — add new series here to expose them in the UI.
- `app.py` — Streamlit entry point. Reads controls from the sidebar (series multiselect, date range), calls `load_data()` (which wraps `DataStore` construction in `@st.cache_data` with a 1-hour TTL), then renders a Plotly line chart and summary metrics per series.

### Adding a new FRED series

Add an entry to `AVAILABLE_SERIES` in `fred_app/store.py` — that's the only change needed for it to appear in the sidebar multiselect.

### Streamlit Cloud deployment

Both apps are deployed via Streamlit Cloud pointing at this repo. The `fred_app/app.py` entry point uses `sys.path.insert` to add the repo root so that `from fred_app.client import ...` resolves correctly regardless of the working directory Streamlit Cloud uses.
