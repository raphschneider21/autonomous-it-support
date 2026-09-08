import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "incidents.db")


def get_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=15)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            id TEXT PRIMARY KEY,
            created_at TEXT NOT NULL,
            user_prompt TEXT NOT NULL,
            category TEXT,
            severity TEXT,
            status TEXT DEFAULT 'open',
            hostname TEXT,
            os_version TEXT,
            resolution_summary TEXT,
            runbook_id TEXT,
            FOREIGN KEY (runbook_id) REFERENCES runbooks(id)
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS runbooks (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            target_os TEXT,
            tags TEXT,
            trigger_signatures TEXT,
            pre_checks TEXT,
            remediation_steps TEXT,
            verification TEXT,
            rollback_plan TEXT,
            created_at TEXT NOT NULL,
            times_executed INTEGER DEFAULT 0,
            times_succeeded INTEGER DEFAULT 0
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            incident_id TEXT NOT NULL,
            timestamp TEXT NOT NULL,
            agent_name TEXT NOT NULL,
            action_type TEXT NOT NULL,
            safety_tier TEXT NOT NULL,
            command_executed TEXT,
            output TEXT,
            user_approved INTEGER DEFAULT 0,
            FOREIGN KEY (incident_id) REFERENCES incidents(id)
        )
    """)

    conn.commit()
    conn.close()


def insert_incident(incident_id: str, user_prompt: str, category: str = None):
    conn = get_connection()
    conn.execute(
        "INSERT INTO incidents (id, created_at, user_prompt, category, status) VALUES (?, ?, ?, ?, ?)",
        (incident_id, datetime.utcnow().isoformat(), user_prompt, category, "open"),
    )
    conn.commit()
    conn.close()


def update_incident(incident_id: str, **kwargs):
    conn = get_connection()
    sets = ", ".join(f"{k} = ?" for k in kwargs)
    values = list(kwargs.values()) + [incident_id]
    conn.execute(f"UPDATE incidents SET {sets} WHERE id = ?", values)
    conn.commit()
    conn.close()


def get_incident(incident_id: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM incidents WHERE id = ?", (incident_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def insert_audit(entry: dict):
    conn = get_connection()
    conn.execute(
        "INSERT INTO audit_log (incident_id, timestamp, agent_name, action_type, safety_tier, command_executed, output, user_approved) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        (
            entry["incident_id"],
            entry["timestamp"],
            entry["agent_name"],
            entry["action_type"],
            entry["safety_tier"],
            entry.get("command_executed"),
            entry.get("output"),
            entry.get("user_approved", 0),
        ),
    )
    conn.commit()
    conn.close()


def get_audit_log(incident_id: str):
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE incident_id = ? ORDER BY timestamp", (incident_id,)
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def insert_runbook(runbook: dict):
    conn = get_connection()
    conn.execute(
        "INSERT OR REPLACE INTO runbooks (id, title, target_os, tags, trigger_signatures, pre_checks, remediation_steps, verification, rollback_plan, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            runbook["id"],
            runbook["title"],
            runbook.get("target_os"),
            runbook.get("tags"),
            runbook.get("trigger_signatures"),
            runbook.get("pre_checks"),
            runbook.get("remediation_steps"),
            runbook.get("verification"),
            runbook.get("rollback_plan"),
            datetime.utcnow().isoformat(),
        ),
    )
    conn.commit()
    conn.close()


def get_all_runbooks():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM runbooks").fetchall()
    conn.close()
    return [dict(r) for r in rows]
