import hashlib
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

_PALETTE = [
    "#1f77b4", "#ff7f0e", "#2ca02c", "#d62728",
    "#9467bd", "#8c564b", "#e377c2", "#7f7f7f",
    "#bcbd22", "#17becf", "#aec7e8", "#ffbb78",
]


def color_for_series(series_id: str) -> str:
    """Deterministic color assignment per series ID — same series always gets same color."""
    h = int(hashlib.md5(series_id.encode()).hexdigest(), 16)
    return _PALETTE[h % len(_PALETTE)]


def single_series_chart(
    df: pd.DataFrame,
    series_id: str,
    units: str,
    height: int = 380,
) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["value"],
            mode="lines",
            name=series_id,
            line=dict(width=2, color=color_for_series(series_id)),
            connectgaps=False,
        )
    )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=units,
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        hovermode="x unified",
        showlegend=False,
    )
    return fig


def dual_axis_chart(
    df: pd.DataFrame,
    series_id: str,
    primary_label: str,
    secondary_label: str = "YoY % Change",
    secondary_col: str = "yoy",
    show_value: bool = True,
    show_secondary: bool = True,
    height: int = 420,
) -> go.Figure:
    """Render a dual-axis chart: raw value (left) and a derived series (right, e.g. YoY %)."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    color = color_for_series(series_id)
    if show_value:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["value"],
                name="Value",
                mode="lines",
                line=dict(width=2, color=color),
                connectgaps=False,
            ),
            secondary_y=False,
        )

    if show_secondary and secondary_col in df.columns:
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df[secondary_col] * 100,
                name=secondary_label,
                mode="lines",
                line=dict(width=2, dash="dash", color="#e08214"),
                connectgaps=False,
            ),
            secondary_y=True,
        )
        fig.add_hline(
            y=0,
            line=dict(dash="dot", color="#95a5a6", width=1),
            secondary_y=True,
        )

    fig.update_layout(
        xaxis_title="Date",
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="right", x=1),
    )
    fig.update_yaxes(title_text=primary_label, secondary_y=False)
    fig.update_yaxes(title_text=secondary_label + " (%)", secondary_y=True)
    return fig


def multi_series_chart(
    series_dfs: dict[str, pd.DataFrame],
    titles: dict[str, str],
    y_label: str,
    base_date=None,
    height: int = 450,
) -> go.Figure:
    """Plot multiple series on a single y-axis. Optionally mark a base date with a vertical line."""
    fig = go.Figure()
    for sid, df in series_dfs.items():
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["value"],
                name=titles.get(sid, sid),
                mode="lines",
                line=dict(width=2, color=color_for_series(sid)),
                connectgaps=False,
            )
        )
    if base_date is not None:
        ts = pd.Timestamp(base_date).isoformat()
        fig.add_shape(
            type="line",
            x0=ts, x1=ts, y0=0, y1=1, yref="paper",
            line=dict(dash="dash", color="#95a5a6", width=1),
        )
        fig.add_annotation(
            x=ts, y=1, yref="paper",
            text="Base", showarrow=False, yanchor="bottom",
            font=dict(color="#95a5a6", size=11),
        )
    fig.update_layout(
        xaxis_title="Date",
        yaxis_title=y_label,
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
    )
    return fig


def mixed_axis_chart(
    primary_dfs: dict[str, pd.DataFrame],
    secondary_dfs: dict[str, pd.DataFrame],
    titles: dict[str, str],
    primary_label: str,
    secondary_label: str,
    base_date=None,
    show_50_line: bool = True,
    height: int = 470,
) -> go.Figure:
    """Plot primary-axis series (solid) and secondary-axis series (dashed) together."""
    fig = make_subplots(specs=[[{"secondary_y": True}]])

    for sid, df in primary_dfs.items():
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["value"],
                name=titles.get(sid, sid),
                mode="lines",
                line=dict(width=2, color=color_for_series(sid)),
                connectgaps=False,
            ),
            secondary_y=False,
        )

    for sid, df in secondary_dfs.items():
        fig.add_trace(
            go.Scatter(
                x=df["date"],
                y=df["value"],
                name=titles.get(sid, sid),
                mode="lines",
                line=dict(width=2, dash="dash", color=color_for_series(sid)),
                connectgaps=False,
            ),
            secondary_y=True,
        )

    if show_50_line and secondary_dfs:
        fig.add_hline(
            y=50,
            line=dict(dash="dot", color="#95a5a6", width=1),
            secondary_y=True,
            annotation_text="Baseline 50",
            annotation_position="right",
        )

    if base_date is not None:
        ts = pd.Timestamp(base_date).isoformat()
        fig.add_shape(
            type="line",
            x0=ts, x1=ts, y0=0, y1=1, yref="paper",
            line=dict(dash="dash", color="#95a5a6", width=1),
        )
        fig.add_annotation(
            x=ts, y=1, yref="paper",
            text="Base", showarrow=False, yanchor="bottom",
            font=dict(color="#95a5a6", size=11),
        )

    fig.update_layout(
        xaxis_title="Date",
        margin=dict(l=0, r=0, t=10, b=0),
        height=height,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.0, xanchor="left", x=0),
    )
    fig.update_yaxes(title_text=primary_label, secondary_y=False)
    fig.update_yaxes(title_text=secondary_label, secondary_y=True)
    return fig


def sparkline(df: pd.DataFrame, series_id: str, height: int = 120) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=df["date"],
            y=df["value"],
            mode="lines",
            line=dict(width=1.5, color=color_for_series(series_id)),
            connectgaps=False,
            hoverinfo="x+y",
        )
    )
    fig.update_layout(
        margin=dict(l=0, r=0, t=0, b=0),
        height=height,
        showlegend=False,
        xaxis=dict(visible=False),
        yaxis=dict(visible=False),
    )
    return fig
