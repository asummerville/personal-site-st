# Database Schema — Supabase

**Status: design complete, migration deferred.** The schema below is ready to execute. The app uses `st.session_state` throughout today; this document is the migration source of truth for when the Supabase milestone arrives.

See also: `CLAUDE.md` → "Session state contracts" for the current in-memory shapes these tables replace.

---

## Why Supabase (and why not now)

**Current limitations of `st.session_state`:**

- Wiped on every browser refresh
- Not shared across devices or users
- Can't persist a project between sessions
- No audit trail of what was escalated, when, using which index

**Portfolio value of a real backend:**

Demonstrating Supabase shows the full stack: data engineering (FRED API) + applied stats (escalation, forecasting) + backend persistence + RLS security. That's a more complete story than Streamlit-only.

**Why defer:** The app's data shapes are still changing (Sprint 2 adds series, Sprint 3 adds forecast results). Migrating to a DB while the schema is in flux creates churn. The right sequencing is: stabilize the URL-state pattern in Sprint 1 (which makes session_state explicit), then migrate one table at a time.

**Migration trigger:** When URL params feel like a workaround rather than a feature — i.e., when a user wants to open a project on a different device — that's the moment to pull the Supabase trigger.

---

## Schema

```sql
-- Saved composite indices
-- Today: st.session_state["custom_indices"][name]
create table custom_indices (
  id          uuid        primary key default gen_random_uuid(),
  user_id     uuid        references auth.users(id) on delete cascade,
  name        text        not null,
  base_date   date        not null,
  weights     jsonb       not null,   -- {"WPU801": 40, "CES2000000003": 35, ...}
  series_ids  text[]      not null,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

-- Saved projects
-- Today: st.session_state["project"] (DataFrame) + esc_project_name + esc_base_date
create table projects (
  id                  uuid        primary key default gen_random_uuid(),
  user_id             uuid        references auth.users(id) on delete cascade,
  name                text        not null,
  base_date           date        not null,
  currency_adjustment jsonb,       -- the F10 adjustment dict, if any
  created_at          timestamptz default now(),
  updated_at          timestamptz default now()
);

-- Project line items
-- Today: rows in the st.session_state["project"] DataFrame
create table project_line_items (
  id          uuid    primary key default gen_random_uuid(),
  project_id  uuid    references projects(id) on delete cascade,
  line_item   text    not null,
  cost        numeric not null,
  cost_type   text    not null check (cost_type in ('Labor', 'Materials', 'Equipment', 'Other')),
  sort_order  int     default 0
);

-- Escalation audit log
-- Today: not persisted at all
create table escalation_runs (
  id               uuid        primary key default gen_random_uuid(),
  user_id          uuid        references auth.users(id) on delete cascade,
  project_id       uuid        references projects(id),
  index_used       text,        -- series_id or custom index name
  factor           numeric,     -- escalation factor applied
  original_total   numeric,
  escalated_total  numeric,
  base_date        date,
  run_date         date,
  created_at       timestamptz default now()
);

-- FRED series cache
-- Today: @st.cache_data (process-lifetime, wiped on restart)
create table fred_series_cache (
  series_id    text        primary key,
  last_fetched timestamptz not null,
  data         jsonb       not null  -- [{"date": "YYYY-MM-DD", "value": X}, ...]
);
```

---

## Row-level security

One representative policy per table. The pattern is identical for all user-owned tables: `auth.uid() = user_id`.

```sql
-- Enable RLS on every table
alter table custom_indices    enable row level security;
alter table projects          enable row level security;
alter table project_line_items enable row level security;
alter table escalation_runs   enable row level security;

-- custom_indices: users own their own rows
create policy "users see own indices"
  on custom_indices for all
  using (auth.uid() = user_id);

-- projects: users own their own rows
create policy "users see own projects"
  on projects for all
  using (auth.uid() = user_id);

-- project_line_items: access granted via parent project ownership
create policy "users see own line items"
  on project_line_items for all
  using (
    exists (
      select 1 from projects p
      where p.id = project_line_items.project_id
        and p.user_id = auth.uid()
    )
  );

-- fred_series_cache: public read (no user-specific data)
create policy "public read cache"
  on fred_series_cache for select
  using (true);

create policy "service role write cache"
  on fred_series_cache for insert, update, delete
  using (auth.role() = 'service_role');
```

**Anonymous-user note:** Until full email auth is added, use Supabase anonymous auth (`supabase.auth.sign_in_anonymously()`). The anonymous session returns a real `auth.uid()`, so all RLS policies work unchanged. Upgrading to email auth later is a one-call operation (`supabase.auth.link_identity()`).

---

## Migration plan (when ready)

1. Create a Supabase project. Copy `SUPABASE_URL` and `SUPABASE_ANON_KEY` into `.env` and Streamlit Cloud secrets.
2. Run the schema SQL above in the Supabase SQL editor.
3. `pip install supabase` and add to `requirements.txt`.
4. Create `fred_app/db.py` — a thin client mirroring `loader.py`'s interface:
   ```python
   from supabase import create_client
   import os

   _client = None

   def get_client():
       global _client
       if _client is None:
           _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_ANON_KEY"])
       return _client
   ```
5. Migrate **Custom Index Builder first** (lowest blast radius): replace `st.session_state["custom_indices"]` reads/writes with `db.get_client().table("custom_indices").select(...)` calls. Keep the session_state as an in-process cache; write-through to Supabase on save.
6. Migrate **Projects** next: replace `st.session_state["project"]` with DB reads/writes. The line items table maps 1:1 to the DataFrame rows.
7. Migrate **FRED cache last**: replace `@st.cache_data` with a DB-backed cache that survives process restarts. Only worth doing if Streamlit Cloud cold starts become noticeably slow.

---

## What we explicitly do NOT store

- Raw FRED data older than 6 months in the cache table (set a cron to prune `last_fetched < now() - interval '6 months'`)
- PII of any kind — no names, emails, or project addresses in line items
- Anything that would make this app feel like a "real" SaaS prematurely — no billing, no usage limits, no admin dashboard until there are actual users

**Cost:** Supabase free tier supports 500 MB storage and 2 active projects — more than sufficient for portfolio scale.
