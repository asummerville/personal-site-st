# Construction Cost Explorer — UI/UX Specification

## Navigation Structure

Built with `st.navigation` (Streamlit 1.36+). Each page is a separate file in `fred_app/pages/`. The sidebar is persistent across all pages and contains a date range picker (default: 10 years to today), series selector grouped by category, and a Reset Filters button.

```
EXPLORE
  └─ Trend: Single Series     (tabs: Linear | With % Change | Time Blocks)
  └─ Trend: Multi-Series      (tabs: Normalized | Mixed Axis)

ANALYZE
  └─ Change Calculator
  └─ Custom Index Builder

ESCALATE
  └─ Project Escalation       (tabs: Single Index | Custom Index)
  └─ Currency Normalization
  └─ Location Normalization   ← v2 (pending location factor dataset)
```

---

## Page Layout Template

Every page follows this structure:

```
[Page title + 1-sentence description]
[Active filters reminder: date range badge, active series count]
────────────────────────────────────
[Primary output — full width: chart or table]
[Secondary outputs — metrics / supporting tables]
[Collapsible section: Raw Data | Methodology Notes]
```

---

## Feature Specifications

---

### F1 — Trend: Single Series › Linear ✓ *implemented*

**Purpose:** View the raw time-series values of one FRED series as a simple line chart to understand the historical trend.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Series | Selectbox (single) | WPU801 |
| Date range | Date range picker | Global sidebar |
| Show recession bands | Checkbox toggle | Off |
| Download data | Button | — |

**Output**
- Full-width Plotly line chart. X-axis: date. Y-axis: native value, label from series `units` metadata.
- Unified hover tooltip: date, value, units.
- Frequency badge (e.g., "Monthly") displayed near chart title.
- Below chart: 5 metric cards — Latest Value | Latest Date | Min | Max | Mean.
- Collapsible raw data table (date, value columns).

**Transforms:** None. Filter `df` to selected date range and plot.

**UX Notes**
- `connectgaps=False` — render data gaps as breaks, never interpolate.
- If fewer than 3 data points in the selected range: warn "Too few data points — try widening the date range."

---

### F2 — Trend: Single Series › Value + Annual % Change ✓ *implemented*

**Purpose:** Show both the raw value and its year-over-year percent change on dual axes, revealing whether costs are accelerating or decelerating.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Series | Selectbox (single) | WPU801 |
| Date range | Date range picker | Global sidebar |
| Smoothing | Selectbox | None / 3-mo rolling / 12-mo rolling |
| Display mode | Toggle | Show both |

**Output**
- Full-width Plotly dual-axis chart.
  - Left y-axis (primary): raw value as a solid line, labeled with native units.
  - Right y-axis (secondary): YoY % change as a dashed line. Zero line rendered as a thin gray dashed rule.
  - Unified hover tooltip showing both values.
- Below chart, two metric column sets:
  - Left: Latest Value, Min, Max, Mean (raw).
  - Right: Latest YoY %, Max YoY %, Min YoY %, Mean YoY %.

**Transforms**
- Monthly series: `yoy = (v_t / v_{t-12}) - 1`
- Quarterly series: `yoy = (v_t / v_{t-4}) - 1`
- If smoothing selected: apply `rolling(N).mean()` to values before computing YoY.
- If `series_type = "rate"` (series already expresses % change, e.g., CPALTT01USM661S): degrade to F1 view and show notice: "This series already expresses % change — YoY transform not applied."

**UX Notes**
- Requires ≥ 12 months of data for a monthly series to render YoY — warn if range is too narrow.
- Display mode toggle: "Show value" / "Show % change" / "Show both" (default: both).

---

### F3 — Trend: Single Series › Time Blocks ✓ *implemented*

**Purpose:** At-a-glance table showing how much a series has changed over standardized backward-looking windows — useful for bid preparation and cost basis decisions.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Series | Selectbox (single) | WPU801 |
| Anchor date | Date picker | Latest available data point |
| Display mode | Radio | % Change |
| Download | Button | — |

**Output**
- Summary table:

  | Period | Start Date | Start Value | End Value | Change | % Change |
  |---|---|---|---|---|---|
  | 3 Months | … | … | … | … | … |
  | 6 Months | … | … | … | … | … |
  | 1 Year | … | … | … | … | … |
  | 2 Years | … | … | … | … | … |
  | 5 Years | … | … | … | … | … |
  | 10 Years | … | … | … | … | … |
  | 20 Years | … | … | … | … | … |

- Conditional formatting: positive % change → green; negative → red. Color intensity scales with magnitude.
- Compact sparkline chart below the table for visual reference.
- Tooltip per row: plain-language description of the window (e.g., "Change from 5 years ago to today").

**Transforms**
- For each window T (months): `start_val = df[date ≤ anchor − T months].iloc[-1]`, `end_val = df[date ≤ anchor].iloc[-1]`, `pct = (end_val / start_val) − 1`.
- For `series_type = "diffusion"`: show absolute point change (`end − start`); label column "Point Change" instead of "% Change."
- If series history is shorter than the window: gray out that row and display "Insufficient data."

**UX Notes**
- Anchor date defaults to the latest available data point, not calendar today, to avoid lag-edge artifacts (many FRED series trail by 1–2 months).

---

### F4 — Trend: Multi-Series › Normalized ✓ *implemented*

**Purpose:** Compare multiple cost series on one chart by normalizing all to a common starting index value, eliminating unit differences and enabling relative performance comparison.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Series | Multi-select checkboxes (max 8, grouped by category) | WPU801, WPUSI012011 |
| Date range | Date range picker | Global sidebar |
| Index base date | Date picker | 10 years ago (Jan 1 of that year) |
| Index base value | Number input | 100 |
| Download | Button | — |

**Output**
- Full-width Plotly line chart. All series on a single y-axis labeled `Index (Base Date = 100)`. Each series a distinct color (see Color System). Vertical dashed line at the base date. Unified hover tooltip.
- Summary table below:

  | Series | Category | Latest Normalized Value | Change Since Base | Avg Annual Change |
  |---|---|---|---|---|

**Transforms**
- For each series: `norm_i(t) = (v_i(t) / v_i(base_date)) × base_value`
- Find `v_i(base_date)` as the nearest prior data point on or before the base date.
- Plot each series at its native frequency — do not interpolate to fill gaps from mixed-frequency series.

**UX Notes**
- If only 1 series selected: prompt to add more or redirect to F1.
- Cap at 8 series — warn and ignore additional selections beyond the limit.
- Warn if selected series have mixed frequencies: "Note: series have mixed frequencies. Each renders at its native frequency."

---

### F5 — Trend: Multi-Series › Mixed Axis ✓ *implemented*

**Purpose:** Support charts combining standard index series with diffusion or baseline-50 series (which cannot be meaningfully rebased) using dual axes.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Primary axis series | Multi-select | Index-type series |
| Secondary axis series | Multi-select | Diffusion/rate series |
| Index base date | Date picker | 10 years ago |
| Secondary axis label | Text input | "Diffusion Index" |
| Date range | Date range picker | Global sidebar |

**Output**
- Full-width Plotly dual-axis chart.
  - Left y-axis: normalized index series (solid lines).
  - Right y-axis: diffusion/rate series in native units (dashed lines).
  - Horizontal reference line at y=50 on right axis labeled "Expansion / Contraction."
  - Legend includes line style (solid vs. dashed) as a visual cue.

**Transforms**
- Primary axis: same normalization as F4.
- Secondary axis: raw values, no transformation.

**UX Notes**
- Auto-assign series to axis by `series_type` metadata (`"diffusion"` or `"rate"` → secondary); user can override.
- If a diffusion series is placed on the primary axis, show inline warning: "This series uses a baseline-50 scale and may not be meaningful as a rebased index."

---

### F6 — Analyze: Change Calculator ✓ *implemented*

**Purpose:** Compute the total cumulative percent change and compound annual growth rate (CAGR) for any series between a user-specified past date and today.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Series | Multi-select (max 5) | WPU801 |
| Start date | Date picker | — |
| End date | Date picker | Latest available data |
| Display format | Radio | % Change |

**Output**
- Results table (one row per series):

  | Series | Start Date | Start Value | End Date | End Value | Total % Change | Years Elapsed | CAGR |
  |---|---|---|---|---|---|---|---|

- Horizontal bar chart: CAGR by series, sorted descending.
- Callout: *"Over X years, [Series] increased Y% total, averaging Z% per year."*
- Copy-to-clipboard button.

**Transforms**
- `start_val` / `end_val`: nearest data point on or before the input date.
- `total_pct = (end_val / start_val) − 1`
- `years = (end_date − start_date).days / 365.25`
- `CAGR = (end_val / start_val)^(1 / years) − 1`
- `series_type = "diffusion"`: absolute point change only; suppress CAGR.
- `series_type = "rate"` (e.g., CPALTT01USM661S): show mean rate over the period and start→end point change (pp). **Do not compound** — these series store annual-percentage values (~3.2 = 3.2%), not monthly multipliers.

**UX Notes**
- If exact date has no data: snap to nearest prior point and show notice "No data on [date] — using [snapped date]."
- Suppress CAGR if `years < 1`; show total % change only.
- Warn if start date predates the series' available history.

---

### F7 — Analyze: Custom Index Builder ✓ *implemented*

**Purpose:** Construct a weighted composite cost index from multiple FRED series, reflecting the specific cost structure of a project type (e.g., heavy civil vs. building construction).

**Inputs**

| Control | Type | Default |
|---|---|---|
| Series | Multi-select | — |
| Weight per series | Slider (0–100) + number input (bidirectional) | Equal split |
| Normalization base date | Date picker | 10 years ago |
| Index name | Text input | "My Custom Index" |
| Save / Load | Buttons | — |

**Output**
- Weight assignment panel: one card per series showing the series name, category badge, weight slider, and a running total displayed as `Total Weight: X / 100` (green when exactly 100, red otherwise).
- Full-width Plotly line chart: composite index as a bold line; component series as lighter lines (toggleable via legend).
- Component breakdown table: Series | Weight | Individual CAGR | Weighted Contribution.

**Transforms**
1. Normalize each series to base date: `norm_i(t) = (v_i(t) / v_i(base_date)) × 100`
2. Composite: `composite(t) = Σ(weight_i × norm_i(t)) / Σ(weight_i)`
3. Mixed frequencies: resample all series to **month-end** (last observation in the month) before weighting. This is the implemented strategy — not "lowest common frequency."

**UX Notes**
- Allow weight editing freely during construction but disable Save/Apply until weights sum to 100.
- "Distribute equally" button: sets each weight to `100 / n`.
- "Normalize to 100" button: rescales existing weights proportionally.
- Saved custom indices persist in `st.session_state` and are available in F8/F9.
- Warn if any component series has gaps: "Gaps in [Series] will propagate to the composite."

---

### F8 — Escalate: Project Escalation › Single Index

**Purpose:** Estimate the current replacement cost of a past project by escalating each line item using a single FRED cost index.

**Inputs**

| Control | Type | Notes |
|---|---|---|
| Project name | Text input | — |
| Base cost date | Date picker | Date original costs were set |
| Escalation index | Selectbox | Single FRED series |
| Cost breakdown | `st.data_editor` | Columns: Line Item, Cost ($), Cost Type |
| Cost Type options | Selectbox column | Labor / Materials / Equipment / Other |
| Add / Remove row | Buttons | — |
| Download report | Button | CSV |

**Output**
- Escalation factor callout (prominent): *"Index on [date]: X.XXXX | Index today: Y.XXXX | Factor: Z.XXXX× (+N% over M years, CAGR: P%)"*
- Results table: Line Item | Cost Type | Original Cost | Escalation Factor | Escalated Cost | Change ($) | Change (%)
- Totals row. Toggle for optional pie chart breakdown. Compact reference chart of the index over the escalation period with base date and today marked.

**Transforms**
- `factor = index_current / index_base` (nearest prior data points for each date).
- `escalated_i = original_i × factor`

**UX Notes**
- If index has no data at the base date: show error and prompt to choose a more recent date or different index.
- Pre-populate a dismissible sample project to demonstrate the tool.
- Factor displayed to 4 decimal places; costs to 2 decimal places.
- Disclaimer: *"Escalation based on national average indices. Regional factors not applied unless using Location Normalization."*

---

### F9 — Escalate: Project Escalation › Custom Index

**Purpose:** Escalate a project cost breakdown using either a saved composite index (from F7) or per-cost-type index assignments, for more granular accuracy.

**Inputs**

All F8 inputs, plus:

| Control | Type | Notes |
|---|---|---|
| Index mode | Radio | "Use Saved Custom Index" / "Assign per Cost Type" |
| Custom index selector | Selectbox | Lists saved indices from F7 |
| Per-type index selectors | Selectbox per cost type | Labor / Materials / Equipment / Other |

**Output**
- Same results table as F8 with an additional column: "Index Used."
- Per-type mode: results grouped by cost type with subtotals.
- Composite escalation summary: *"Weighted average escalation: Z.XXXX× (+N%)"*
- Side-by-side comparison callout: "Single Index vs. Custom Index" totals.

**Transforms**
- Mode A (saved composite): `factor = composite_current / composite_base`.
- Mode B (per-type): `factor_i = index_i_current / index_i_base` per line item based on its Cost Type.
- Weighted average factor: `Σ(escalated_costs) / Σ(original_costs)`.

**UX Notes**
- Default per-type assignments (user-overridable): Labor → CES2000000003, Materials → WPUSI012011, Equipment → WPU112, Other → WPU801.
- Warn if an assigned index has no data at the base date.
- Per-type mapping is also saveable to `st.session_state`.

---

### F10 — Escalate: Currency Normalization

**Purpose:** Convert a project cost from a foreign currency to USD at the historical exchange rate so that escalation is applied in consistent USD terms.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Source currency | Selectbox | USD, EUR, GBP, CAD, AUD, JPY, BRL |
| Target currency | Selectbox | USD |
| Conversion date | Date picker | — |
| Project cost | Number input | — |
| Data source | Radio | FRED bilateral rate / Manual entry |
| Manual rate override | Number input | Shown only if "Manual entry" |
| Apply to project | Toggle | Off |
| Swap currencies | Button | — |

**Output**
- Conversion result card: *"[X] [CCY] on [date] → $[Y] USD at rate [R]"*
- FX rate chart: Plotly line chart, ±2-year window around the conversion date, vertical marker at conversion date.
- If applied: "Updated Project Cost" card showing the USD-normalized cost that feeds into F8/F9.
- Workflow order callout: **Currency Normalization → Location Normalization → Escalation**.

**Transforms**
- Use bilateral FRED FX series. FRED conventions (document in `notes` field per series):
  - `DEXUSEU`: USD per EUR → `converted = foreign_EUR × rate`
  - `DEXCAUS`: CAD per USD → `converted = foreign_CAD / rate`
  - `DEXJPUS`: JPY per USD → `converted = foreign_JPY / rate`
  - `DEXBZUS`: BRL per USD → `converted = foreign_BRL / rate`
  - `DEXUSUK`: USD per GBP → `converted = foreign_GBP × rate`
  - `DEXUSAL`: USD per AUD → `converted = foreign_AUD × rate`
- Manual entry: user-provided rate, direction specified by the source→target currency labels shown in the UI.

**Data Model Change Required**
Add bilateral FX series to `AVAILABLE_SERIES` in `store.py` under a `"Currency"` category: `DEXUSEU`, `DEXCAUS`, `DEXJPUS`, `DEXBZUS`, `DEXUSUK`, `DEXUSAL`. Document conversion direction in the `notes` metadata field for each.

---

### F11 — Escalate: Location Normalization *(v2 — deferred)*

**Purpose:** Adjust project costs from one city/region to another using location cost factors before escalation.

**Status:** Deferred to v2. Requires a bundled location factor lookup table (RSMeans City Cost Index or ENR BCI, ~700+ cities) that is not yet available. The spec below is complete for implementation once the dataset is sourced.

**Inputs**

| Control | Type | Default |
|---|---|---|
| Origin location | Selectbox | National Average (LF = 1.00) |
| Target location | Selectbox | — |
| Data source | Radio | Built-in table / Manual entry |
| Manual factor | Number input | Shown if "Manual entry" |
| Factor type | Radio | Overall / Split (Labor + Materials) |
| Apply to project | Toggle | Off |

**Output**
- Factor display card: *"[Origin] LF: X.XX | [Target] LF: Y.YY | Relative Factor: Z.ZZ (+/− N%)"*
- Adjusted cost table: Line Item | Original Cost | Location Factor | Adjusted Cost.
- Reference map (v2+): static choropleth of relative cost levels by city/region.

**Transforms**
- `relative_factor = target_LF / origin_LF`
- `adjusted_i = original_i × relative_factor`
- Split mode: apply `labor_LF` to labor line items, `materials_LF` to materials line items based on Cost Type.

**UX Notes**
- National Average (LF = 1.00) is always available regardless of data source.
- Warn: *"Location factors are survey-based and may lag current market conditions."*
- Helper link to RSMeans / ENR for manual entry reference.

---

## Data Model Additions

The following fields must be added to `SeriesMeta` in `fred_app/store.py`. These fields gate behavior across multiple features.

| Field | Type | Values | Used In |
|---|---|---|---|
| `series_type` | `str` | `"index"`, `"diffusion"`, `"rate"`, `"count"`, `"currency"` | F2, F3, F5, F6 |
| `base_year` | `int \| None` | e.g., `1982`, `2005`, or `None` | F4, F7 axis labels |
| `frequency_periods` | `int` | `12` (monthly), `4` (quarterly), `1` (annual) | F2 YoY shift |
| `yoy_applicable` | `bool` | `False` for diffusion and rate series | F2 guard |

---

## App-Wide UX Conventions

### Color System
- Series colors assigned by series ID (not selection order) from a 12-color qualitative palette — colors remain consistent across all pages.
- Positive change: `#2ecc71` (green)
- Negative change: `#e74c3c` (red)
- Reference / neutral lines: `#95a5a6` (gray)

### Session State Keys

| Key | Type | Purpose |
|---|---|---|
| `selected_series` | `list[str]` | Active FRED series IDs |
| `date_range` | `tuple[date, date]` | Global date filter |
| `custom_indices` | `dict[str, CustomIndex]` | Saved custom index configs |
| `project` | `ProjectBreakdown` | Current project cost breakdown |
| `currency_adjustment` | `CurrencyAdjustment` | Applied FX normalization |
| `location_adjustment` | `LocationAdjustment` | Applied location factor (v2) |

### Error States
- No data in selected range: empty state illustration + "Try widening your date range" prompt.
- Series load failure: inline `st.warning` with retry button. Never a blocking modal.
- Invalid inputs (weights ≠ 100, date out of range, etc.): `st.warning` inline on the relevant control; do not disable or block the rest of the page.

---

## Planned File Structure

```
fred_app/
├── app.py                    # Entry point + st.navigation
├── store.py                  # SeriesMeta (extended), DataStore, AVAILABLE_SERIES
├── client.py                 # FredClient (unchanged)
├── utils/
│   └── transforms.py         # YoY, CAGR, normalization, escalation factor math
├── components/
│   └── charts.py             # Shared Plotly chart builder functions
└── pages/
    ├── trend_single.py       # F1, F2, F3 (tabs)
    ├── trend_multi.py        # F4, F5 (tabs)
    ├── change_calculator.py  # F6
    ├── custom_index.py       # F7
    ├── escalation.py         # F8, F9 (tabs)
    ├── currency.py           # F10
    └── location.py           # F11 (v2)
```
