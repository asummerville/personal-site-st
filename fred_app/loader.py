from datetime import date
import streamlit as st

from fred_app.client import FredClient
from fred_app.store import AVAILABLE_SERIES, DataStore


@st.cache_data(ttl=3600, show_spinner="Fetching data from FRED…")
def load_series(series_ids: tuple[str, ...], start: date, end: date) -> DataStore:
    """Fetch the requested series from FRED and return a populated DataStore.

    Errors per series are caught and surfaced as warnings; partial results
    still return so other series remain usable.
    """
    client = FredClient()
    store = DataStore()
    for sid in series_ids:
        if sid not in AVAILABLE_SERIES:
            continue
        try:
            df = client.fetch_series(sid, start=start, end=end)
            store.add(sid, df, AVAILABLE_SERIES[sid])
        except Exception as e:
            st.warning(f"Could not fetch {sid}: {e}")
    return store
