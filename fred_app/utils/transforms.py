from datetime import date, datetime
from dateutil.relativedelta import relativedelta
import pandas as pd


def snap_to_date(df: pd.DataFrame, target: date | datetime) -> pd.Series | None:
    """Return the row of df whose date is the latest on or before `target`.

    Returns None if no data exists before `target`.
    """
    if df is None or df.empty:
        return None
    ts = pd.Timestamp(target)
    mask = df["date"] <= ts
    if not mask.any():
        return None
    return df.loc[mask].iloc[-1]


def yoy_change(df: pd.DataFrame, periods: int = 12) -> pd.DataFrame:
    """Return a copy of df with an added `yoy` column = (v_t / v_{t-periods}) - 1.

    `periods` should match the series frequency (12 monthly, 4 quarterly, 1 annual).
    """
    out = df.copy()
    out["yoy"] = out["value"].pct_change(periods=periods)
    return out


def normalize_to_base(
    df: pd.DataFrame, base_date: date | datetime, base_value: float = 100.0
) -> pd.DataFrame:
    """Rebase a series so that the value at `base_date` equals `base_value`.

    Uses the nearest data point on or before `base_date` as the anchor.
    Returns a copy with the original `value` column replaced by the normalized values.
    """
    anchor = snap_to_date(df, base_date)
    if anchor is None or anchor["value"] == 0:
        out = df.copy()
        out["value"] = float("nan")
        return out
    out = df.copy()
    out["value"] = (out["value"] / anchor["value"]) * base_value
    return out


def total_pct_change(
    df: pd.DataFrame, start: date | datetime, end: date | datetime
) -> dict | None:
    """Return total % change between snapped start and end dates plus the anchor values."""
    s = snap_to_date(df, start)
    e = snap_to_date(df, end)
    if s is None or e is None or s["value"] == 0:
        return None
    return {
        "start_date": s["date"],
        "start_value": s["value"],
        "end_date": e["date"],
        "end_value": e["value"],
        "total_pct": (e["value"] / s["value"]) - 1.0,
        "abs_change": e["value"] - s["value"],
    }


def cagr(start_value: float, end_value: float, years: float) -> float | None:
    """Compound annual growth rate. Returns None when not meaningful (years<=0, neg/zero values)."""
    if years <= 0 or start_value <= 0 or end_value <= 0:
        return None
    return (end_value / start_value) ** (1.0 / years) - 1.0


_TIME_BLOCKS: list[tuple[str, relativedelta]] = [
    ("3 Months", relativedelta(months=3)),
    ("6 Months", relativedelta(months=6)),
    ("1 Year", relativedelta(years=1)),
    ("2 Years", relativedelta(years=2)),
    ("5 Years", relativedelta(years=5)),
    ("10 Years", relativedelta(years=10)),
    ("20 Years", relativedelta(years=20)),
]


def time_block_changes(
    df: pd.DataFrame, anchor: date | datetime, mode: str = "pct"
) -> pd.DataFrame:
    """Build a summary table of value/% change over standard backward-looking windows.

    `mode` is "pct" (return % change) or "point" (absolute change, for diffusion series).
    Returns a DataFrame with one row per period, with "Insufficient data" rows when
    the series doesn't go back far enough.
    """
    rows = []
    anchor_ts = pd.Timestamp(anchor)
    end_row = snap_to_date(df, anchor_ts)

    for label, delta in _TIME_BLOCKS:
        start_ts = anchor_ts - delta
        start_row = snap_to_date(df, start_ts)
        if start_row is None or end_row is None:
            rows.append(
                {
                    "Period": label,
                    "Start Date": "—",
                    "Start Value": None,
                    "End Value": None,
                    "Change": None,
                    "% Change": None,
                    "_insufficient": True,
                }
            )
            continue

        change = end_row["value"] - start_row["value"]
        pct = (end_row["value"] / start_row["value"]) - 1.0 if start_row["value"] else None
        rows.append(
            {
                "Period": label,
                "Start Date": start_row["date"].strftime("%Y-%m-%d"),
                "Start Value": round(float(start_row["value"]), 4),
                "End Value": round(float(end_row["value"]), 4),
                "Change": round(float(change), 4),
                "% Change": pct,
                "_insufficient": False,
            }
        )

    out = pd.DataFrame(rows)
    if mode == "point":
        out = out.drop(columns=["% Change"])
        out = out.rename(columns={"Change": "Point Change"})
    return out
