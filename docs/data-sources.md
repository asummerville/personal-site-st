# Data Sources

Free public data worth pulling in. FRED series IDs are directly usable via the existing `FredClient` / `AVAILABLE_SERIES` pattern in `fred_app/store.py`. Non-FRED sources note their ingestion method.

---

## Tier 1 — Add in Sprint 2 (Materials sub-indices)

These extend the existing materials coverage with commodity-level granularity. All monthly. All available via FRED with the existing client.

| Series ID | Name | Units | Why a cost consultant cares | Effort |
|---|---|---|---|---|
| `WPU081` | PPI: Lumber & Wood Products | Index | Major driver of residential + light commercial framing costs; spiked 3× in 2021 | S |
| `WPU101` | PPI: Iron & Steel Mill Products | Index | Structural steel, rebar; foundational for heavy construction | S |
| `WPU102` | PPI: Nonferrous Metals | Index | Copper (MEP), aluminum (cladding, glazing) | S |
| `WPU0571` | PPI: Asphalt & Asphalt Products | Index | Road paving; proxy for petroleum-derived materials broadly | S |
| `WPU1322` | PPI: Flat Glass | Index | Curtain wall, glazing; volatile in supply disruptions | S |
| `WPU13` | PPI: Plastics & Rubber Products | Index | Piping, waterproofing, MEP conduit | S |
| `WPU061` | PPI: Industrial Chemicals | Index | Waterproofing, adhesives, coatings | S |
| `PCU212321212321` | PPI: Construction Sand, Gravel & Crushed Stone | Index | Concrete aggregate; regional availability affects price | S |
| `WPU057303` | PPI: No. 2 Diesel Fuel | Index | Equipment operating cost; haul-road fuel; direct project cost | S |
| `WPU0561` | PPI: Crude Petroleum | Index | Upstream driver of asphalt, plastics, transport | S |

**How to add:** In `fred_app/store.py`, append to `AVAILABLE_SERIES`:

```python
SeriesMeta(
    series_id="WPU081",
    title="PPI: Lumber & Wood Products",
    units="Index",
    frequency="Monthly",
    category="Materials",
    series_type="index",
    base_year=1982,
    frequency_periods=12,
    yoy_applicable=True,
),
```

The series appears automatically in Trend pages, Change Calculator, and Custom Index Builder. For the Materials page (Sprint 2), add `category="Materials"` and filter by `m.category == "Materials"` when building the sparkline grid.

---

## Tier 2 — Demand-side & leading indicators

Demand-side series contextualize cost trends. Rising starts → tighter labor + materials supply → upward cost pressure. These are correlation tools, not escalation indices.

| Series ID | Name | Frequency | Why it matters | Effort |
|---|---|---|---|---|
| `HOUST` | Housing Starts: Total | Monthly | The most-watched leading indicator for residential construction volume | S |
| `PERMIT` | New Private Housing Units Authorized | Monthly | Permits lead starts by 1–3 months; earlier signal | S |
| `TLPRVCONS` | Total Private Construction Spending | Monthly | Dollar volume of work in place; demand barometer | S |
| `DGS10` | 10-Year Treasury Constant Maturity | Daily | Financing cost proxy; affects developer feasibility | S |
| `MORTGAGE30US` | 30-Year Fixed Mortgage Rate | Weekly | Residential demand driver | S |
| AIA ABI | Architecture Billings Index | Monthly | Leads non-residential construction 9–12 months; **not on FRED** — free monthly CSV from [aia.org](https://www.aia.org/resources/8116-architecture-billings-index) | M |

**Note on AIA ABI:** The ABI is available as a free monthly press release (CSV or PDF) from the AIA website. It requires a small ingestion script or manual CSV upload. High domain value — it is the standard leading indicator for non-residential construction and would differentiate the app significantly.

---

## Tier 3 — Regional & sectoral breakouts

| Series Pattern | Example | Name | Effort |
|---|---|---|---|
| `*CONS` | `CACONS`, `NYCONS`, `TXCONS` | State construction employment | S per state — filter on `category="Regional"` |
| Regional CPI | `CUURA101SA0` (Northeast) | Regional cost-of-living context for labor | M |
| State unemployment | `*UR` | State-level slack indicator | S |

Adding state construction employment for 5–10 key states (CA, NY, TX, FL, WA) is low effort and enables a "where are workers?" lens relevant for projects with tight labor markets.

---

## Tier 4 — Non-FRED public data

These require ingestion work beyond the FRED client but are free and publicly available.

| Source | What | Access | Effort | Domain value |
|---|---|---|---|---|
| **BLS API** (api.bls.gov) | Finer-grained PPI sub-items, ECI splits, regional employment | Free API key; `requests`-based client | M | 5 |
| **Census Construction** | Monthly construction spending by type (residential, commercial, public) | Free CSV download | S | 4 |
| **FHWA NHCCI** | National Highway Construction Cost Index — quarterly | Free quarterly PDF/CSV | M | 4 |
| **Turner Building Cost Index** | Quarterly non-residential building costs | Free quarterly PDF; manual or parse | M | 4 |
| **Mortenson Cost Index** | Quarterly regional construction costs | Free quarterly PDF | M | 3 |
| **World Bank Pink Sheet** | Global commodity prices (monthly CSV) | Public URL, no auth | S | 3 |
| **LME free tier** | Metal spot prices (last 3 months) | Scrape or free API endpoint | M | 3 |

**BLS API note:** The BLS API requires a free key (register at api.bls.gov). It surfaces series that FRED doesn't carry, including more granular OES occupation-wage data and state-level ECI splits. Worth adding a `BLSClient` alongside `FredClient` in Sprint 2 or later.

---

## Tier 5 — Stretch / parked

| Source | What | Blocker |
|---|---|---|
| DOE EIA State Energy Prices | Natural gas + electricity by state — direct project cost for energy-intensive buildings | Free API; low priority until regional features arrive |
| NOAA weather | HDD/CDD for weather-adjusted escalation factors | High complexity; marginal value for most projects |
| Procore / CostX actual costs | Real committed cost vs. index-predicted cost | OAuth required; enterprise only |
| Dodge Data | Construction starts by project type | Paywalled |
| RSMeans | Unit cost benchmarks | Paywalled |

---

## Currently in `AVAILABLE_SERIES`

For reference — series already wired up as of F1–F10:

| Series ID | Name | Category | Type |
|---|---|---|---|
| `WPU801` | PPI: Construction Cost Index | Cost Indices | index |
| `WPUSI012011` | PPI: Construction Materials & Components | Materials | index |
| `CES2000000003` | Construction: Avg Hourly Earnings | Labor | index |
| `ECICONWAG` | Employment Cost Index: Construction | Labor | index |
| `WPU112` | PPI: Construction Machinery & Equipment | Equipment | index |
| `TTLCONS` | Total Construction Spending | Spending | count |
| `CPALTT01USM661S` | CPI: All Items (YoY rate) | Prices | rate |
| `UNRATE` | Unemployment Rate | Labor | rate |
| `LNU04032230` | Construction Unemployment Rate | Labor | rate |
| `USCONS` | Construction Employment | Labor | count |
| `DEXUSEU` | USD/EUR exchange rate | FX | currency |
| `DEXUSUK` | USD/GBP exchange rate | FX | currency |
| `DEXUSAL` | USD/AUD exchange rate | FX | currency |
| `DEXCAUS` | CAD/USD exchange rate | FX | currency |
| `DEXJPUS` | JPY/USD exchange rate | FX | currency |
| `DEXBZUS` | BRL/USD exchange rate | FX | currency |
