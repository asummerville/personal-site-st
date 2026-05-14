import os
from datetime import date
import pandas as pd
from fredapi import Fred
from dotenv import load_dotenv

load_dotenv()


class FredClient:
    def __init__(self):
        api_key = os.getenv("FRED_API_KEY")
        if not api_key:
            raise EnvironmentError("FRED_API_KEY not set. Add it to your .env file.")
        self._fred = Fred(api_key=api_key)

    def fetch_series(
        self,
        series_id: str,
        start: date | None = None,
        end: date | None = None,
    ) -> pd.DataFrame:
        """Return a tidy DataFrame with columns [date, value] for a FRED series."""
        raw = self._fred.get_series(
            series_id,
            observation_start=start,
            observation_end=end,
        )
        df = raw.reset_index()
        df.columns = ["date", "value"]
        df["date"] = pd.to_datetime(df["date"])
        df = df.dropna(subset=["value"])
        return df

    def fetch_series_info(self, series_id: str) -> dict:
        """Return metadata dict for a series (title, units, frequency, etc.)."""
        info = self._fred.get_series_info(series_id)
        return info.to_dict()
