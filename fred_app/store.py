from dataclasses import dataclass, field
from datetime import date
import pandas as pd


@dataclass
class SeriesMeta:
    series_id: str
    title: str
    units: str
    frequency: str
    category: str = "General"
    notes: str = ""


# To add a new FRED series, add an entry here — it will appear automatically in the UI.
AVAILABLE_SERIES: dict[str, SeriesMeta] = {
    # ── Cost Indices ──────────────────────────────────────────────────────────
    "WPU801": SeriesMeta(
        series_id="WPU801",
        title="Construction Cost Index (PPI)",
        units="Index 1982=100",
        frequency="Monthly",
        category="Cost Indices",
    ),
    "CPALTT01USM661S": SeriesMeta(
        series_id="CPALTT01USM661S",
        title="Consumer Price Index (All Items)",
        units="Growth Rate Previous Period",
        frequency="Monthly",
        category="Cost Indices",
    ),
    # ── Labor ─────────────────────────────────────────────────────────────────
    "CES2000000003": SeriesMeta(
        series_id="CES2000000003",
        title="Construction: Average Hourly Earnings",
        units="Dollars per Hour",
        frequency="Monthly",
        category="Labor",
    ),
    "ECICONWAG": SeriesMeta(
        series_id="ECICONWAG",
        title="Employment Cost Index: Wages & Salaries (Construction)",
        units="Index 2001=100",
        frequency="Quarterly",
        category="Labor",
    ),
    "CES2000000001": SeriesMeta(
        series_id="CES2000000001",
        title="US Construction Employees (Total)",
        units="Thousands of Persons",
        frequency="Monthly",
        category="Labor",
    ),
    "JTS2300JOL": SeriesMeta(
        series_id="JTS2300JOL",
        title="US Construction Job Openings (JOLTS)",
        units="Level in Thousands",
        frequency="Monthly",
        category="Labor",
    ),
    "LNS14032230": SeriesMeta(
        series_id="LNS14032230",
        title="US Construction Unemployment Rate",
        units="Percent",
        frequency="Monthly",
        category="Labor",
    ),
    # ── Materials ─────────────────────────────────────────────────────────────
    "WPUSI012011": SeriesMeta(
        series_id="WPUSI012011",
        title="PPI: Construction Materials & Components",
        units="Index 1982=100",
        frequency="Monthly",
        category="Materials",
    ),
    "WPU1017": SeriesMeta(
        series_id="WPU1017",
        title="PPI: Steel Mill Products",
        units="Index 1982=100",
        frequency="Monthly",
        category="Materials",
    ),
    "PCU327320327320": SeriesMeta(
        series_id="PCU327320327320",
        title="PPI: Ready-Mix Concrete",
        units="Index 2005=100",
        frequency="Monthly",
        category="Materials",
    ),
    # ── Equipment ─────────────────────────────────────────────────────────────
    "WPU112": SeriesMeta(
        series_id="WPU112",
        title="PPI: Construction Machinery & Equipment",
        units="Index 1982=100",
        frequency="Monthly",
        category="Equipment",
    ),
    # ── Spending ──────────────────────────────────────────────────────────────
    "TTLCONS": SeriesMeta(
        series_id="TTLCONS",
        title="Total Construction Spending",
        units="Millions of Dollars",
        frequency="Monthly",
        category="Spending",
    ),
    # ── Currency ──────────────────────────────────────────────────────────────
    "DTWEXBGS": SeriesMeta(
        series_id="DTWEXBGS",
        title="Trade Weighted US Dollar Index (Broad)",
        units="Index Jan 2006=100",
        frequency="Daily",
        category="Currency",
    ),
}

CATEGORIES: list[str] = sorted({m.category for m in AVAILABLE_SERIES.values()})


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
