from dataclasses import dataclass, field
from datetime import date
import pandas as pd


@dataclass
class SeriesMeta:
    series_id: str
    title: str
    units: str
    frequency: str
    notes: str = ""


# Series available in the app; extend this list to add more.
AVAILABLE_SERIES: dict[str, SeriesMeta] = {
    "GDP": SeriesMeta(
        series_id="GDP",
        title="Gross Domestic Product",
        units="Billions of Dollars",
        frequency="Quarterly",
    ),
    "UNRATE": SeriesMeta(
        series_id="UNRATE",
        title="Unemployment Rate",
        units="Percent",
        frequency="Monthly",
    ),
    "CPIAUCSL": SeriesMeta(
        series_id="CPIAUCSL",
        title="Consumer Price Index (All Items)",
        units="Index 1982-84=100",
        frequency="Monthly",
    ),
    "FEDFUNDS": SeriesMeta(
        series_id="FEDFUNDS",
        title="Federal Funds Effective Rate",
        units="Percent",
        frequency="Monthly",
    ),
}


@dataclass
class DataStore:
    """Holds fetched FRED series keyed by series ID."""
    series: dict[str, pd.DataFrame] = field(default_factory=dict)
    meta: dict[str, SeriesMeta] = field(default_factory=dict)

    def add(self, series_id: str, df: pd.DataFrame, meta: SeriesMeta) -> None:
        self.series[series_id] = df
        self.meta[series_id] = meta

    def get(self, series_id: str) -> pd.DataFrame | None:
        return self.series.get(series_id)

    def summary(self, series_id: str) -> dict:
        df = self.series.get(series_id)
        if df is None or df.empty:
            return {}
        v = df["value"]
        return {
            "Latest Value": round(v.iloc[-1], 2),
            "Latest Date": df["date"].iloc[-1].strftime("%Y-%m-%d"),
            "Min": round(v.min(), 2),
            "Max": round(v.max(), 2),
            "Mean": round(v.mean(), 2),
        }
