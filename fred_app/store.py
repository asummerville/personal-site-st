from dataclasses import dataclass, field
from datetime import date
import pandas as pd


# series_type values gate behavior across pages:
#   "index"     — rebasable index (PPI, ECI, etc.)
#   "rate"      — already a % / growth rate (skip YoY transform)
#   "count"     — absolute level (employees, openings)
#   "diffusion" — baseline-50 indicator (no natural rebase)
#   "currency"  — bilateral exchange rate
@dataclass
class SeriesMeta:
    series_id: str
    title: str
    units: str
    frequency: str
    category: str = "General"
    series_type: str = "index"
    base_year: int | None = None
    frequency_periods: int = 12
    yoy_applicable: bool = True
    notes: str = ""


AVAILABLE_SERIES: dict[str, SeriesMeta] = {
    # ── Cost Indices ──────────────────────────────────────────────────────────
    "WPU801": SeriesMeta(
        series_id="WPU801",
        title="Construction Cost Index (PPI)",
        units="Index 1982=100",
        frequency="Monthly",
        category="Cost Indices",
        series_type="index",
        base_year=1982,
        frequency_periods=12,
    ),
    "CPALTT01USM661S": SeriesMeta(
        series_id="CPALTT01USM661S",
        title="Consumer Price Index (Growth Rate)",
        units="Growth Rate Previous Period",
        frequency="Monthly",
        category="Cost Indices",
        series_type="rate",
        frequency_periods=12,
        yoy_applicable=False,
        notes="Already expresses period-over-period growth; YoY transform not applicable.",
    ),
    # ── Labor ─────────────────────────────────────────────────────────────────
    "CES2000000003": SeriesMeta(
        series_id="CES2000000003",
        title="Construction: Average Hourly Earnings",
        units="Dollars per Hour",
        frequency="Monthly",
        category="Labor",
        series_type="count",
        frequency_periods=12,
    ),
    "ECICONWAG": SeriesMeta(
        series_id="ECICONWAG",
        title="Employment Cost Index: Wages & Salaries (Construction)",
        units="Index 2001=100",
        frequency="Quarterly",
        category="Labor",
        series_type="index",
        base_year=2001,
        frequency_periods=4,
    ),
    "CES2000000001": SeriesMeta(
        series_id="CES2000000001",
        title="US Construction Employees (Total)",
        units="Thousands of Persons",
        frequency="Monthly",
        category="Labor",
        series_type="count",
        frequency_periods=12,
    ),
    "JTS2300JOL": SeriesMeta(
        series_id="JTS2300JOL",
        title="US Construction Job Openings (JOLTS)",
        units="Level in Thousands",
        frequency="Monthly",
        category="Labor",
        series_type="count",
        frequency_periods=12,
    ),
    "LNS14032230": SeriesMeta(
        series_id="LNS14032230",
        title="US Construction Unemployment Rate",
        units="Percent",
        frequency="Monthly",
        category="Labor",
        series_type="rate",
        frequency_periods=12,
        yoy_applicable=False,
    ),
    # ── Materials ─────────────────────────────────────────────────────────────
    "WPUSI012011": SeriesMeta(
        series_id="WPUSI012011",
        title="PPI: Construction Materials & Components",
        units="Index 1982=100",
        frequency="Monthly",
        category="Materials",
        series_type="index",
        base_year=1982,
        frequency_periods=12,
    ),
    "WPU1017": SeriesMeta(
        series_id="WPU1017",
        title="PPI: Steel Mill Products",
        units="Index 1982=100",
        frequency="Monthly",
        category="Materials",
        series_type="index",
        base_year=1982,
        frequency_periods=12,
    ),
    "PCU327320327320": SeriesMeta(
        series_id="PCU327320327320",
        title="PPI: Ready-Mix Concrete",
        units="Index 2005=100",
        frequency="Monthly",
        category="Materials",
        series_type="index",
        base_year=2005,
        frequency_periods=12,
    ),
    # ── Equipment ─────────────────────────────────────────────────────────────
    "WPU112": SeriesMeta(
        series_id="WPU112",
        title="PPI: Construction Machinery & Equipment",
        units="Index 1982=100",
        frequency="Monthly",
        category="Equipment",
        series_type="index",
        base_year=1982,
        frequency_periods=12,
    ),
    # ── Spending ──────────────────────────────────────────────────────────────
    "TTLCONS": SeriesMeta(
        series_id="TTLCONS",
        title="Total Construction Spending",
        units="Millions of Dollars",
        frequency="Monthly",
        category="Spending",
        series_type="count",
        frequency_periods=12,
    ),
    # ── Currency ──────────────────────────────────────────────────────────────
    "DTWEXBGS": SeriesMeta(
        series_id="DTWEXBGS",
        title="Trade Weighted US Dollar Index (Broad)",
        units="Index Jan 2006=100",
        frequency="Daily",
        category="Currency",
        series_type="index",
        base_year=2006,
        frequency_periods=252,
    ),
    "DEXUSEU": SeriesMeta(
        series_id="DEXUSEU",
        title="USD / EUR Exchange Rate",
        units="USD per EUR",
        frequency="Daily",
        category="Currency",
        series_type="currency",
        frequency_periods=252,
        yoy_applicable=False,
        notes="USD per 1 EUR. To convert EUR → USD: amount × rate.",
    ),
    "DEXCAUS": SeriesMeta(
        series_id="DEXCAUS",
        title="CAD / USD Exchange Rate",
        units="CAD per USD",
        frequency="Daily",
        category="Currency",
        series_type="currency",
        frequency_periods=252,
        yoy_applicable=False,
        notes="CAD per 1 USD. To convert CAD → USD: amount / rate.",
    ),
    "DEXJPUS": SeriesMeta(
        series_id="DEXJPUS",
        title="JPY / USD Exchange Rate",
        units="JPY per USD",
        frequency="Daily",
        category="Currency",
        series_type="currency",
        frequency_periods=252,
        yoy_applicable=False,
        notes="JPY per 1 USD. To convert JPY → USD: amount / rate.",
    ),
    "DEXBZUS": SeriesMeta(
        series_id="DEXBZUS",
        title="BRL / USD Exchange Rate",
        units="BRL per USD",
        frequency="Daily",
        category="Currency",
        series_type="currency",
        frequency_periods=252,
        yoy_applicable=False,
        notes="BRL per 1 USD. To convert BRL → USD: amount / rate.",
    ),
    "DEXUSUK": SeriesMeta(
        series_id="DEXUSUK",
        title="USD / GBP Exchange Rate",
        units="USD per GBP",
        frequency="Daily",
        category="Currency",
        series_type="currency",
        frequency_periods=252,
        yoy_applicable=False,
        notes="USD per 1 GBP. To convert GBP → USD: amount × rate.",
    ),
    "DEXUSAL": SeriesMeta(
        series_id="DEXUSAL",
        title="USD / AUD Exchange Rate",
        units="USD per AUD",
        frequency="Daily",
        category="Currency",
        series_type="currency",
        frequency_periods=252,
        yoy_applicable=False,
        notes="USD per 1 AUD. To convert AUD → USD: amount × rate.",
    ),
}

CATEGORIES: list[str] = sorted({m.category for m in AVAILABLE_SERIES.values()})


def series_by_category(category: str) -> dict[str, SeriesMeta]:
    return {sid: m for sid, m in AVAILABLE_SERIES.items() if m.category == category}


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
