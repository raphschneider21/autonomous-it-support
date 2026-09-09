import yaml
import os
import json
from typing import Optional

RUNBOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "runbooks")

# --- Cache: avoid re-reading + re-parsing YAML from disk on every incident ---
_cached_runbooks: list[dict] = None
_cache_mtime: float = None


def load_runbook(yaml_path: str) -> dict:
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


def _runbooks_changed() -> bool:
    """Return True if any runbook YAML file changed on disk since we cached."""
    if not os.path.exists(RUNBOOKS_DIR):
        return _cached_runbooks is not None
    latest = max(
        (os.path.getmtime(os.path.join(RUNBOOKS_DIR, f))
         for f in os.listdir(RUNBOOKS_DIR) if f.endswith((".yaml", ".yml"))),
        default=0.0,
    )
    return latest > _cache_mtime


def load_all_runbooks() -> list[dict]:
    """Load (and cache) all runbooks from disk.

    The first call reads and parses every YAML file. Subsequent calls reuse
    the cached list until a runbook file changes on disk. This removes a
    repeated disk-I/O + parse cost per incident (the matcher calls this on
    every incident).
    """
    global _cached_runbooks, _cache_mtime

    if _cached_runbooks is not None and not _runbooks_changed():
        return _cached_runbooks

    runbooks = []
    if os.path.exists(RUNBOOKS_DIR):
        for filename in os.listdir(RUNBOOKS_DIR):
            if filename.endswith((".yaml", ".yml")):
                path = os.path.join(RUNBOOKS_DIR, filename)
                runbooks.append(load_runbook(path))

    _cached_runbooks = runbooks
    _cache_mtime = max(
        (os.path.getmtime(os.path.join(RUNBOOKS_DIR, f))
         for f in os.listdir(RUNBOOKS_DIR) if f.endswith((".yaml", ".yml"))),
        default=0.0,
    )
    return runbooks


def runbook_to_db_format(rb: dict) -> dict:
    return {
        "id": rb.get("runbook_id", ""),
        "title": rb.get("title", ""),
        "target_os": rb.get("target_os", ""),
        "tags": json.dumps(rb.get("tags", [])),
        "trigger_signatures": json.dumps(rb.get("trigger_signatures", {})),
        "pre_checks": json.dumps(rb.get("pre_checks", [])),
        "remediation_steps": json.dumps(rb.get("remediation_steps", [])),
        "verification": json.dumps(rb.get("verification", [])),
        "rollback_plan": json.dumps(rb.get("rollback_plan", [])),
    }


def seed_runbooks_db() -> int:
    """Sync the YAML fixture runbooks into the SQLite `runbooks` table.

    The engine matches against the YAML store; this keeps the database view
    (exposed via GET /api/runbooks) consistent with it. Idempotent
    (INSERT OR REPLACE). Returns the number of runbooks seeded.
    """
    from ..database import insert_runbook

    runbooks = load_all_runbooks()
    for rb in runbooks:
        insert_runbook(runbook_to_db_format(rb))
    return len(runbooks)
