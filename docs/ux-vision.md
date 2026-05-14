# UX Vision — Construction Cost Explorer

## The persona

**Maya** is a senior cost consultant at a large engineering firm. She manages 3 active capital programs simultaneously — a hospital, a data center, and a public transit project — each in a different phase. She spends 60% of her week defending or refining cost positions: presenting to clients, responding to PM questions, calibrating estimates against current market conditions.

Her core recurring questions:
- "What's that cost worth today?" (escalation backward)
- "What will it cost at completion?" (escalation forward — the one she can't answer confidently today)
- "Is that spike in materials real or noise?" (trend discernment)
- "What index did we use for the original estimate?" (audit trail)

She is not a data scientist. She doesn't want to configure a model. She wants to type in a number, pick a date, and see a defensible answer with a citation. She hates 7-tab Excel models and she has no patience for dashboards that take 30 seconds to load.

**What Maya needs from this app:** An answer in under a minute, citation-ready, exportable. Every design decision should be tested against that bar.

---

## Design principles

### 1. Always cite the data

Every number on screen should be one click away from "which FRED series, snapped to which date, fetched when?" The methodology expanders (already on every page) are the model. Never show an escalation factor without showing the underlying index values.

This is also a portfolio signal: it shows the builder understands that data provenance matters professionally, not just technically.

### 2. Default to the answer, not the controls

A first-time visitor should see a complete, meaningful result before they touch a single widget. This means:
- Sample project pre-populated in Project Escalation (3 line items, realistic cost split)
- Default series selections that make sense together (not just "first in the list")
- Date range defaulting to a span that shows a clear trend, not today-only

Controls are progressive disclosure. The "power user" settings should be collapsed or secondary — not the first thing you see.

### 3. The chart is the headline

Tables are reference material. The line chart is the deliverable — the thing Maya screenshots and drops into a client deck. Chart quality is therefore a first-class concern:
- Clean axes, no clutter
- Deterministic colors per series (already implemented via `color_for_series`)
- Composite/highlight lines in `#ff4b4b` (Streamlit accent) — distinguishable from component lines in both light and dark mode
- No grid lines heavier than the data lines

### 4. Dark mode is real, not an afterthought

Every color in every chart must be tested in both Streamlit themes. Rules already in CLAUDE.md:
- Never use `color="#111"` or `color="#fff"` for chart elements
- Use `#ff4b4b` for bold/composite/highlight lines
- Plotly `paper_bgcolor` and `plot_bgcolor` should be `"rgba(0,0,0,0)"` (transparent), not hardcoded light or dark values

The lesson from the custom index composite line invisible in dark mode: never assume a color looks good in both themes without checking.

### 5. Persistence by URL, not by login

A shared link should reproduce a full result — no account required. This is Sprint 1's job. The implication for all design decisions: encode the "interesting state" (which series, which date range, which project inputs) into URL params. The session_state pattern already exists; URL encoding is the layer above it.

This principle also means: never put a "you must log in to see this" gate in front of a core feature. The app is a portfolio piece for a public audience. Auth is a future nice-to-have, not a prerequisite.

---

## Navigation evolution

### Today (shipped)
```
Sidebar nav:
  Explore
    Trend: Single Series
    Trend: Multi-Series
  Analyze
    Change Calculator
    Custom Index Builder
  Escalate
    Project Escalation
    Currency Normalization
```

Simple and functional. The groups make logical sense to someone who already knows what they're looking for. The friction: a new user doesn't know where to start.

### 6 months (post-Sprint 2–3)
```
Sidebar nav:
  [Dashboard]   ← new landing page
  Explore
    Trend: Single Series
    Trend: Multi-Series
    Materials     ← new (Sprint 2)
  Analyze
    Change Calculator
    Custom Index Builder
  Escalate
    Project Escalation
    Currency Normalization
  [Library]     ← new group: saved indices, saved projects
```

The Dashboard landing page shows: headline cost indices (WPU801, WPUSI012011, CES2000000003) with 12-month sparklines and YoY % callouts. Recent projects (from session or URL state). Quick-nav tiles to each section.

The Library group appears once saved indices/projects have a real home (URL-encoded in Sprint 1; Supabase-backed later).

### 12 months (post-Supabase)
```
Top-level concept: Projects are first-class objects.

Projects list → Project detail tabs:
  Overview · Cost Breakdown · Escalation · Forecast · Report
```

Each project becomes a workspace. The current "enter project inputs" flow in F8/F9 becomes the Overview tab. Escalation and Forecast get their own tabs. The Report tab generates the PDF. This is the mature UX — Maya opens her hospital project and navigates within it, rather than re-entering data on each page.

This horizon requires Supabase. Don't attempt it before the migration is complete.

---

## Visual language

**Colors:**
- Per-series: deterministic hash via `color_for_series(sid)` in `fred_app/components/charts.py` — same series always gets the same color across all pages
- Composite / highlight lines: `#ff4b4b` (Streamlit accent red) — never use for regular series lines
- Never hardcode `#111`, `#fff`, `#000`, `white`, or `black` for chart elements — use transparent backgrounds and let Streamlit's theme handle the surface

**Typography:**
- Streamlit defaults everywhere. No custom fonts until everything else is polished — font choices are a distraction until the data and interactions are right.

**Density:**
- 3 controls per row max on desktop (`st.columns([1,1,1])`)
- Single-column layout under 768px (Streamlit sidebar collapse handles most of this automatically)
- Methodology expanders stay collapsed by default — don't open them by default just because they're interesting

---

## Onboarding moments

**First load:** A dismissible `st.info` banner on the landing page / first-visited page: "Live data from FRED. No account required. Try loading a sample project to see what's possible." Dismissed via a session_state flag.

**Empty states:** Every `st.multiselect` with no items selected should have a `placeholder=` or a sibling `st.caption` pointing the user toward the next action. "Select a series above to see the chart" is more helpful than a blank panel.

**Methodology expanders:** Already on every page — keep this pattern. The expander label should name the specific transform: "How the escalation factor is calculated" not "Methodology". Specificity signals competence.

---

## Anti-patterns to avoid

**No AI assistant widget.** The data and the math are the value. An LLM chat box would add visual noise, latency, and the risk of hallucinated numbers — the worst possible failure mode for a cost tool.

**No modal dialogs.** Streamlit doesn't do modals cleanly, and they break the mental model of a single-page tool. Use `st.warning`, `st.info`, or `st.expander` for all secondary information.

**No "loading…" without context.** Every FRED fetch should show `st.spinner("Fetching [series name] from FRED...")`. The current `loader.py` pattern does this via `st.warning` for errors; extend it to loading states.

**No feature flags or beta tags.** If a feature isn't ready, don't show it. A half-finished page is worse than a missing page for a portfolio viewer.

**No tables as the primary output.** Tables belong in expanders or below the main chart. The chart is always the lead.

---

## Reference

- `docs/roadmap.md` — which navigation changes ship in which sprint
- `docs/data-sources.md` — Sprint 2 Materials page data
- `docs/feature-backlog.md` — UX polish items ranked by effort
