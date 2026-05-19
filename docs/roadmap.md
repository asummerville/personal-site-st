# Roadmap — Construction Cost Explorer

## Strategic framing

This app exists at the intersection of three disciplines: data engineering (live FRED API, caching, multi-source alignment), applied statistics (YoY transforms, CAGR, ETS forecasting), and domain UX for cost consultants. The portfolio value is not "I know Streamlit" — it is "I understand the workflow of a senior consultant defending a cost position, and I built the tool they'd actually use."

The target persona is Maya: a senior cost consultant on a multi-year capital program, fielding "what does that cost today?" questions from PMs and clients daily. She doesn't have time to re-run an Excel model. She needs citation-ready output in under a minute. That tension — rigor vs. speed — is the design constraint every sprint should test itself against.

The 8-week plan below ships two or three meaningful improvements, not ten half-finished ones. Each sprint has a single deployable deliverable with a clear before/after story.

---

## Sprint 1 — Weeks 1–2: Persistent state via URL

**Why this first:** Right now, every browser refresh wipes custom indices and project inputs. That is the single biggest "this is a toy" tell. Fixing it requires no backend and no auth — just encoding session state into URL query params.

**What ships:**
- `st.query_params` read/write on the Custom Index Builder: a saved index serializes to a compact URL param (`?idx=WPU801:40,CES2000000003:35,WPU112:25&base=2020-01-01`). Visiting the URL restores the index automatically.
- Same treatment on Project Escalation: project name, base date, and line items encode to URL params so a shared link reproduces a full escalation result.
- A "Copy link" button on both pages (copies `st.get_option("browser.serverAddress") + current URL` to clipboard via `st.components.v1.html`).
- No backend. No auth. Pure URL state.

**Definition of done:** Deploy to Streamlit Cloud. Share a link. Open in a fresh incognito tab. See the same result.

**What this demonstrates:** State management without a server; thoughtful UX for a shareable deliverable.

---

## Sprint 2 — Weeks 3–4: Materials sub-indices drill-down

**Why this next:** The app currently has broad PPI indices but no granularity. A real cost consultant asks "is the lumber spike driving this?" before they can advise. Sub-indices give the app domain depth.

**What ships:**
- 10–12 new FRED series in `store.py` (see `data-sources.md` Tier 1 list): lumber, iron/steel, nonferrous metals, asphalt, glass, plastic, industrial chemicals, sand/gravel, diesel, crude petroleum.
- A new **Materials** page under the Explore group in `app.py`. Layout: a grid of small sparkline charts (one per sub-index), each showing the last 12 months of % change, color-coded green/amber/red by trailing 3-month trend. Below the grid: a multi-select to pull any sub-index into a full comparison chart.
- The existing Trend: Multi-Series page picks up the new series automatically (they appear in `AVAILABLE_SERIES`).

**Definition of done:** Deploy. Open Materials page with no series selected and see a populated grid with real data.

**What this demonstrates:** Domain knowledge of construction cost drivers; data engineering for a larger series registry; small-multiples chart pattern.

---

## Sprint 3 — Weeks 5–6: Forecasting overlay

**Why this matters most:** Escalation backward (base date → today) is useful. Escalation forward (today → target completion date) is what a PM actually signs off on. Adding a short-horizon forecast is the single highest-leverage feature for domain credibility and portfolio differentiation.

**What ships:**
- `statsmodels` `ETSModel` (exponential triple smoothing) trained on the trailing 36 months of the selected series. Forecast horizon: 1–36 months (slider). Output: point forecast + 80%/95% confidence bands.
- Overlay added to **Trend: Single Series** as an optional toggle ("Show forecast"). The chart extends the x-axis to the forecast horizon with a dashed line + shaded confidence band.
- Same overlay on **Project Escalation** → Single Index tab: an "Estimated cost at project completion" metric using the forecasted index value at the target date.
- Methodology expander on both pages explaining ETS, the training window, and the confidence interval formula — citation-ready.
- `statsmodels` added to `requirements.txt`.

**Definition of done:** Deploy. On the Single Series page, toggle the forecast for WPU801. See a dashed line + shaded band extending 12 months. On Project Escalation, change the target date to 18 months out and see the "Estimated at completion" metric update.

**What this demonstrates:** Applied time-series statistics; uncertainty communication; consultant-grade deliverable design.

---

## Sprint 4 — Weeks 7–8: Reporting + cross-page wiring

**Why now:** After Sprint 3, the app can produce a complete escalation story: historical trend, current cost, forward forecast. Sprint 4 makes that story exportable and wires the remaining cross-page state (F10 currency → F8/F9 escalation).

**What ships:**
- **PDF export** on Project Escalation: a "Download Report" button generates a one-page PDF (ReportLab) containing project name, base date, escalation factor, escalated total, and the escalation chart as an embedded PNG. Filename: `{project_name}_{today}.pdf`.
- **F10 → F8/F9 wiring**: if `st.session_state["currency_adjustment"]` is set and the project currency is non-USD, the escalation summary shows a "FX-adjusted total" row using the stored conversion rate and the current session's USD equivalent.
- **Forecast vs. spot callout** on Project Escalation: when a Sprint 3 forecast is available, show a `st.info` callout: "Spot escalation: +12.3%. Forecast to [target date]: +15.1%. Using forecast." The user can toggle which to use.
- `reportlab` added to `requirements.txt`.

**Definition of done:** Deploy. On Project Escalation with a real project, click "Download Report". Open the PDF. See correct numbers and the chart. Also set a currency adjustment in F10, return to F8, and see the FX-adjusted row appear automatically.

**What this demonstrates:** Deliverable polish; full cross-page data flow; practical PDF generation.

---

## Shipped pre-sprint (before Week 1)

The following features were built during the planning + POC sessions and are already live on Streamlit Cloud. They represent the baseline the 8-week roadmap builds on.

**Supabase persistence (db.py)**
- `custom_indices` and `projects` / `project_line_items` tables created and migrated automatically on first run.
- Custom Index Builder saves/loads/deletes composite indices to DB; falls back to session-state-only when `CONNECTION_STRING` is absent.
- Project Escalation saves/loads/deletes projects including all line items with their per-item escalation index.
- Save uses PK-based UPDATE for existing projects (avoids duplicate rows on rename).
- Data editor widget state is cleared on Open/Save to prevent stale edit deltas from shadowing DB data.

**Per-line-item escalation (Line Item tab)**
- Each row in the project cost table has an "Escalation Index" `SelectboxColumn` (any eligible FRED series).
- Auto-fill: blank cells default to cost-type-appropriate indices on each render.
- New "Line Item" tab on Project Escalation shows per-row factors, totals, metrics, and a bar chart coloured by assigned index.
- Eliminates the need for the Custom Index → per-type mode for projects with heterogeneous steel/concrete/labor cost splits.

**Saved project picker relocated**
- Moved from sidebar to an inline picker above the project name/date inputs, matching the "open or create" mental model.

---

## Cut from this window

The following are documented in `feature-backlog.md` and explicitly deferred beyond Week 8:

- **Monte Carlo escalation** — valuable, but the ETS confidence bands in Sprint 3 cover the "show uncertainty" use case for now.
- **Regional CCI / F11** — needs a location factor dataset (no clean free source identified yet).
- **AIA ABI lagged indicator** — free monthly CSV, but requires manual ingestion pipeline; park until Sprint 2 data infrastructure is in place.
- **Multi-user / saved workspaces** — Supabase already wired; deferred until there's a reason to need per-user isolation.

---

## Reference

- `docs/feature-backlog.md` — full prioritized list
- `docs/data-sources.md` — Sprint 2 series list
- `docs/database-schema.md` — Supabase schema when ready
- `docs/ux-vision.md` — design principles and navigation evolution
