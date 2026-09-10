"""Ticket store for the monitoring service.

Deliberately a *separate* database from the endpoint/runtime state. In the
current graded demo both services run on the same Mac, but they remain separate
processes with separate SQLite data and communicate over HTTP. The managed
endpoint represented by the runtime is the simulated Ubuntu 26.04 endpoint
`ubuntu-demo-01`, not the Mac host.

A ticket is keyed by `incident_id`, so the endpoint can report the same incident
repeatedly as it progresses and the row is upserted rather than duplicated.
That keeps ingestion idempotent and preserves the architectural boundary that
would also apply if the endpoint service moved to another machine later.
"""
import json
import os
import sqlite3
from datetime import datetime, timezone

from .presentation import presentation

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "tickets.db")

# Lifecycle. `open` and `diagnosing` are live; the rest are terminal.
OPEN_STATES = ("open", "diagnosing")
TERMINAL_STATES = ("closed", "escalated")
ALL_STATES = OPEN_STATES + TERMINAL_STATES


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS tickets (
                incident_id       TEXT PRIMARY KEY,
                hostname          TEXT,
                title             TEXT,
                status            TEXT NOT NULL,
                category          TEXT,
                severity          TEXT,
                user_prompt       TEXT,
                runbook_id        TEXT,
                resolution        TEXT,
                agent_source      TEXT,
                latency_ms        REAL,
                tool_calls        INTEGER,
                tokens_in         INTEGER DEFAULT 0,
                tokens_out        INTEGER DEFAULT 0,
                actions_json      TEXT DEFAULT '[]',
                errors_json       TEXT DEFAULT '[]',
                escalation_json   TEXT,
                user_confirmed    TEXT,
                -- Optional documentation, sent by the endpoint when available.
                -- Both are nullable: a ticket reported early in the lifecycle
                -- has neither, and must still ingest and render.
                incident_report   TEXT,
                runbook_json      TEXT,
                created_at        TEXT NOT NULL,
                updated_at        TEXT NOT NULL
            )
        """)
        # Additive migration for ticket databases created before the
        # documentation fields existed.
        existing = {r[1] for r in conn.execute("PRAGMA table_info(tickets)").fetchall()}
        for column in ("incident_report", "runbook_json"):
            if column not in existing:
                conn.execute(f"ALTER TABLE tickets ADD COLUMN {column} TEXT")

        conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_status ON tickets(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_tickets_updated ON tickets(updated_at DESC)")


def upsert_ticket(payload: dict) -> dict:
    """Create or update the ticket for an incident. Idempotent by incident_id."""
    incident_id = payload["incident_id"]
    now = _now()

    existing = get_ticket(incident_id)
    created_at = existing["created_at"] if existing else now

    # Documentation arrives late in the lifecycle and is not repeated on every
    # snapshot. A later update that omits it must not wipe what we already have.
    for field, prior in (("incident_report", "incident_report"), ("runbook", "runbook")):
        if existing and payload.get(field) in (None, "", {}) and existing.get(prior):
            payload[field] = existing[prior]

    row = {
        "incident_id": incident_id,
        "hostname": payload.get("hostname"),
        "title": payload.get("title") or (payload.get("user_prompt") or "")[:120],
        "status": payload.get("status", "open"),
        "category": payload.get("category"),
        "severity": payload.get("severity"),
        "user_prompt": payload.get("user_prompt"),
        "runbook_id": payload.get("runbook_id"),
        "resolution": payload.get("resolution"),
        "agent_source": payload.get("agent_source"),
        "latency_ms": payload.get("latency_ms"),
        "tool_calls": payload.get("tool_calls"),
        "tokens_in": payload.get("tokens_in", 0),
        "tokens_out": payload.get("tokens_out", 0),
        "actions_json": json.dumps(payload.get("actions", [])),
        "errors_json": json.dumps(payload.get("errors", [])),
        "escalation_json": json.dumps(payload["escalation"]) if payload.get("escalation") else None,
        "user_confirmed": payload.get("user_confirmed"),
        "incident_report": payload.get("incident_report"),
        "runbook_json": json.dumps(payload["runbook"]) if payload.get("runbook") else None,
        "created_at": created_at,
        "updated_at": now,
    }

    with get_connection() as conn:
        conn.execute(f"""
            INSERT OR REPLACE INTO tickets ({", ".join(row)})
            VALUES ({", ".join(":" + k for k in row)})
        """, row)

    return get_ticket(incident_id)


def _hydrate(row: sqlite3.Row) -> dict:
    ticket = dict(row)
    ticket["actions"] = json.loads(ticket.pop("actions_json") or "[]")
    ticket["errors"] = json.loads(ticket.pop("errors_json") or "[]")
    escalation = ticket.pop("escalation_json")
    ticket["escalation"] = json.loads(escalation) if escalation else None
    runbook = ticket.pop("runbook_json", None)
    ticket["runbook"] = json.loads(runbook) if runbook else None
    ticket.update(presentation(ticket))
    return ticket


def get_ticket(incident_id: str):
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM tickets WHERE incident_id = ?", (incident_id,)
        ).fetchone()
    return _hydrate(row) if row else None


def list_tickets(status: str = None, limit: int = 200) -> list[dict]:
    query = "SELECT * FROM tickets"
    params: list = []
    if status and status != "all":
        if status == "open":
            query += f" WHERE status IN ({','.join('?' * len(OPEN_STATES))})"
            params.extend(OPEN_STATES)
        else:
            query += " WHERE status = ?"
            params.append(status)
    query += " ORDER BY updated_at DESC LIMIT ?"
    params.append(limit)

    with get_connection() as conn:
        rows = conn.execute(query, params).fetchall()
    return [_hydrate(r) for r in rows]


def stats() -> dict:
    """Headline numbers for the dashboard.

    `false_resolution_rate` is the one worth watching: the agent verified its
    own fix technically, and the user said the problem was still there anyway.
    That gap is invisible without asking, and it is the most damaging failure a
    support tool has.
    """
    with get_connection() as conn:
        rows = conn.execute("SELECT status, user_confirmed FROM tickets").fetchall()
        agg = conn.execute("""
            SELECT AVG(latency_ms) AS avg_latency,
                   SUM(tokens_in)  AS tokens_in,
                   SUM(tokens_out) AS tokens_out
            FROM tickets
        """).fetchone()

    counts = {"open": 0, "closed": 0, "escalated": 0}
    for r in rows:
        if r["status"] in OPEN_STATES:
            counts["open"] += 1
        elif r["status"] in counts:
            counts[r["status"]] += 1

    verified_but_unresolved = sum(1 for r in rows if r["user_confirmed"] == "still_broken")
    confirmed = sum(1 for r in rows if r["user_confirmed"] in ("solved", "still_broken"))

    total = len(rows)
    return {
        "total": total,
        "open": counts["open"],
        "closed": counts["closed"],
        "escalated": counts["escalated"],
        "auto_resolution_rate": round(counts["closed"] / total, 3) if total else 0.0,
        "false_resolution_rate": round(verified_but_unresolved / confirmed, 3) if confirmed else 0.0,
        "confirmations": confirmed,
        "avg_latency_ms": round(agg["avg_latency"], 1) if agg["avg_latency"] else 0.0,
        "tokens_in": agg["tokens_in"] or 0,
        "tokens_out": agg["tokens_out"] or 0,
    }
