"""
Thin Supabase/PostgreSQL persistence layer for the Construction Cost Explorer.

Requires CONNECTION_STRING in .env (locally) or Streamlit Cloud secrets.
If the variable is absent the app degrades gracefully to session_state-only mode.

Connection string format (Supabase transaction pooler recommended for Cloud):
  postgresql://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres

Tables managed here:
  custom_indices      — saved composite indices (from Custom Index Builder)
  projects            — saved project metadata (from Project Escalation)
  project_line_items  — line items belonging to a project
"""

import json
import os
from contextlib import contextmanager

import psycopg2
import psycopg2.extras
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

_DSN: str | None = os.getenv("CONNECTION_STRING")


# ── Connection ────────────────────────────────────────────────────────────────

def is_available() -> bool:
    return bool(_DSN)


@contextmanager
def _cursor():
    """Short-lived connection → RealDictCursor → commit/rollback → close."""
    if not _DSN:
        raise RuntimeError("CONNECTION_STRING not set")
    conn = psycopg2.connect(_DSN)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


# ── Schema ────────────────────────────────────────────────────────────────────

@st.cache_resource(show_spinner=False)
def _init_schema() -> bool:
    """Run once per server process. Creates tables if absent."""
    if not _DSN:
        return False
    try:
        conn = psycopg2.connect(_DSN)
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS custom_indices (
                    id         BIGSERIAL PRIMARY KEY,
                    name       TEXT        NOT NULL,
                    base_date  DATE        NOT NULL,
                    weights    JSONB       NOT NULL,
                    series_ids TEXT[]      NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS projects (
                    id         BIGSERIAL PRIMARY KEY,
                    name       TEXT        NOT NULL,
                    base_date  DATE        NOT NULL,
                    created_at TIMESTAMPTZ DEFAULT NOW(),
                    updated_at TIMESTAMPTZ DEFAULT NOW()
                )
            """)
            cur.execute("""
                CREATE TABLE IF NOT EXISTS project_line_items (
                    id         BIGSERIAL PRIMARY KEY,
                    project_id BIGINT      REFERENCES projects(id) ON DELETE CASCADE,
                    line_item  TEXT        NOT NULL,
                    cost       NUMERIC     NOT NULL,
                    cost_type  TEXT        NOT NULL
                                          CHECK (cost_type IN ('Labor','Materials','Equipment','Other')),
                    sort_order INT         DEFAULT 0
                )
            """)
        conn.commit()
        conn.close()
        return True
    except Exception as exc:
        st.warning(f"DB schema init failed: {exc}")
        return False


def ensure_schema() -> bool:
    """Call from any page that uses the DB. Returns True if DB is ready."""
    return _init_schema()


# ── Custom Indices ─────────────────────────────────────────────────────────────

def list_custom_indices() -> list[dict]:
    """Return all saved composite indices, newest first."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT id, name, base_date, weights, series_ids, created_at "
                "FROM custom_indices ORDER BY created_at DESC"
            )
            rows = cur.fetchall()
        return [
            {
                "db_id": r["id"],
                "name": r["name"],
                "base_date": r["base_date"].isoformat(),
                "weights": r["weights"],          # already a dict (psycopg2 parses JSONB)
                "series_ids": list(r["series_ids"]),
                "created_at": r["created_at"],
            }
            for r in rows
        ]
    except Exception:
        return []


def save_custom_index(
    name: str,
    base_date: str,
    weights: dict[str, float],
    series_ids: list[str],
) -> int | None:
    """Insert or update a custom index by name. Returns the row id."""
    try:
        with _cursor() as cur:
            # Upsert: if a row with this name exists, overwrite it.
            cur.execute(
                """
                INSERT INTO custom_indices (name, base_date, weights, series_ids)
                VALUES (%s, %s::date, %s::jsonb, %s)
                ON CONFLICT DO NOTHING
                RETURNING id
                """,
                (name, base_date, json.dumps(weights), series_ids),
            )
            row = cur.fetchone()
            if row:
                return row["id"]
            # Name already exists — update it.
            cur.execute(
                """
                UPDATE custom_indices
                SET base_date = %s::date, weights = %s::jsonb,
                    series_ids = %s, created_at = NOW()
                WHERE name = %s
                RETURNING id
                """,
                (base_date, json.dumps(weights), series_ids, name),
            )
            row = cur.fetchone()
            return row["id"] if row else None
    except Exception as exc:
        st.warning(f"DB save failed: {exc}")
        return None


def delete_custom_index(db_id: int) -> bool:
    try:
        with _cursor() as cur:
            cur.execute("DELETE FROM custom_indices WHERE id = %s", (db_id,))
        return True
    except Exception:
        return False


# ── Projects ──────────────────────────────────────────────────────────────────

def list_projects() -> list[dict]:
    """Return all saved project headers, newest first."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT id, name, base_date, created_at, updated_at "
                "FROM projects ORDER BY updated_at DESC"
            )
            rows = cur.fetchall()
        return [
            {
                "db_id": r["id"],
                "name": r["name"],
                "base_date": r["base_date"].isoformat(),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            }
            for r in rows
        ]
    except Exception:
        return []


def save_project(
    name: str,
    base_date: str,
    line_items: list[dict],       # each: {line_item, cost, cost_type}
) -> int | None:
    """Upsert a project and its line items. Returns the project id."""
    try:
        with _cursor() as cur:
            # Check for existing project with this name.
            cur.execute("SELECT id FROM projects WHERE name = %s", (name,))
            existing = cur.fetchone()
            if existing:
                project_id = existing["id"]
                cur.execute(
                    "UPDATE projects SET base_date = %s::date, updated_at = NOW() WHERE id = %s",
                    (base_date, project_id),
                )
                cur.execute("DELETE FROM project_line_items WHERE project_id = %s", (project_id,))
            else:
                cur.execute(
                    "INSERT INTO projects (name, base_date) VALUES (%s, %s::date) RETURNING id",
                    (name, base_date),
                )
                project_id = cur.fetchone()["id"]

            # Insert line items.
            for i, item in enumerate(line_items):
                cur.execute(
                    """
                    INSERT INTO project_line_items (project_id, line_item, cost, cost_type, sort_order)
                    VALUES (%s, %s, %s, %s, %s)
                    """,
                    (project_id, item["line_item"], item["cost"], item["cost_type"], i),
                )
        return project_id
    except Exception as exc:
        st.warning(f"DB save failed: {exc}")
        return None


def load_project(project_id: int) -> dict | None:
    """Return project metadata + line items list, or None on failure."""
    try:
        with _cursor() as cur:
            cur.execute(
                "SELECT id, name, base_date FROM projects WHERE id = %s", (project_id,)
            )
            proj = cur.fetchone()
            if not proj:
                return None
            cur.execute(
                "SELECT line_item, cost, cost_type FROM project_line_items "
                "WHERE project_id = %s ORDER BY sort_order",
                (project_id,),
            )
            items = cur.fetchall()
        return {
            "db_id": proj["id"],
            "name": proj["name"],
            "base_date": proj["base_date"].isoformat(),
            "line_items": [dict(r) for r in items],
        }
    except Exception:
        return None


def delete_project(db_id: int) -> bool:
    try:
        with _cursor() as cur:
            cur.execute("DELETE FROM projects WHERE id = %s", (db_id,))
        return True
    except Exception:
        return False
