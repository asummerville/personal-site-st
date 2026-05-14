# Feature Backlog

All ideas that didn't make the 8-week roadmap. Pull from this list when planning the next sprint. Ratings: Effort S/M/L; Portfolio value 1–5; Domain value 1–5.

---

## Forecasting & projections

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| Short-horizon ETS forecast on Single Series | M | 5 | 5 | Sprint 3 candidate |
| Forecast overlay on Project Escalation ("escalated cost in 2026?") | M | 5 | 5 | Sprint 3 candidate |
| Multi-scenario forecast (low/base/high) using percentile bands | S | 4 | 5 | Extend Sprint 3 |
| Forecast accuracy backtest — "how well did this index forecast 5 years ago?" | M | 4 | 4 | Strong portfolio story: honest about model limits |
| ARIMA as an alternative model with BIC comparison | L | 3 | 3 | Probably overkill; ETS is enough for cost escalation |

---

## Risk & sensitivity

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| Monte Carlo on escalation factor | L | 4 | 5 | Run N simulations using historical σ; show distribution of escalated totals |
| Sensitivity table — "what if labor jumps 8% vs 4%?" | M | 3 | 5 | High domain value; consultant staple |
| Series volatility ranking on Trend pages | S | 3 | 3 | Color-code or rank series by 12-month rolling σ |
| Correlation matrix of tracked series | M | 3 | 4 | Useful for custom index design — are your chosen series actually independent? |

---

## Benchmarking & context

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| Cost-per-SF benchmark library | L | 4 | 5 | Needs a user-contributed dataset; Supabase-dependent |
| Compare two projects side-by-side | M | 3 | 4 | Same page, two project columns |
| Cohort lens: how does this look vs. median data center / hospital / school? | L | 4 | 5 | Requires benchmark data; park until DB milestone |

---

## Reporting & deliverables

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| PDF export of escalation report | M | 4 | 5 | Sprint 4 candidate; ReportLab |
| Shareable URL with encoded state | S | 5 | 4 | Sprint 1 candidate |
| Email-ready summary template (copy-paste HTML) | S | 3 | 4 | Low effort, surprisingly useful in practice |
| Power BI / Excel-shaped CSV exports | S | 2 | 4 | Just add a `st.download_button` with the right column names |
| Word doc export via python-docx | M | 2 | 4 | Low portfolio value; Excel CSV is simpler and more flexible |

---

## Materials & data depth

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| Materials sub-indices page | M | 4 | 5 | Sprint 2 candidate — see `data-sources.md` Tier 1 |
| Energy / fuel price ribbon on relevant pages | S | 3 | 4 | Diesel and crude already in Tier 1; small chart above main chart |
| AIA ABI lagged-indicator overlay | S | 4 | 5 | Free monthly CSV from AIA; shows demand-side pressure 6–9 months ahead |
| Tariff / trade-policy news annotations on relevant series | L | 4 | 4 | Manual annotation DB or news API; high maintenance |

---

## UX polish

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| Homepage / dashboard tile view | M | 4 | 3 | Headline indices, last updated, quick-nav tiles |
| First-time visitor tour (dismissible modal or callout) | S | 4 | 2 | `st.session_state` flag for "first visit"; show once |
| Dark-mode visual QA pass | S | 3 | 2 | Already mostly correct; audit all pages systematically |
| Mobile-responsive review (sidebar collapse) | M | 3 | 2 | Streamlit 1.36 sidebar collapse works; test real breakpoints |
| Keyboard-navigable series selector | M | 3 | 3 | `st.multiselect` with search is the standard; nothing extra needed |

---

## Persistence & multi-user (Supabase milestone)

| Idea | Effort | Domain | Notes |
|---|---|---|---|
| Save / list / open saved projects | M | 5 | Supabase `projects` + `project_line_items` tables |
| Saved-index library | M | 5 | Supabase `custom_indices` table |
| Anonymous-user session UUID | S | 4 | UUID in `st.query_params`; row-level ownership without auth |
| Share a project by link | S | 5 | UUID → public read Supabase RLS policy |
| Escalation run history | M | 4 | `escalation_runs` audit log; "what did I quote last month?" |

---

## Integrations (parked)

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| Procore cost-data webhook | L | 3 | 4 | Pulls actual committed costs; needs Procore OAuth |
| Slack / Teams "weekly escalation digest" cron | M | 4 | 3 | `apscheduler` + Slack webhook; demo-friendly |
| Google Sheets sync for project line items | M | 3 | 4 | `gspread`; practical for firms that live in Sheets |
| Power Automate connector | L | 2 | 3 | Enterprise-only; not worth it for portfolio |

---

## Domain-specific data layers

| Idea | Effort | Portfolio | Domain | Notes |
|---|---|---|---|---|
| Regional CCI (F11) | L | 4 | 5 | Needs location factor dataset; no clean free source yet |
| FHWA NHCCI quarterly overlay | S | 3 | 4 | Free CSV; highway/infrastructure focus |
| Turner Building Cost Index | S | 3 | 4 | Free quarterly PDF; may need manual entry |
| World Bank commodity prices (Pink Sheet) | M | 3 | 3 | Monthly CSV; global coverage for international projects |
| DOE EIA energy prices by state | M | 3 | 4 | Free API; useful for energy-intensive project types |
