"""Runbook store: loading, caching and parameter resolution.

The knowledge base is organised into **stores** so several endpoint platforms
can coexist without one polluting the other's retrieval results:

    fixtures/runbooks/                 -> store "default"      (Windows fixtures)
    fixtures/runbooks/ubuntu-26.04/    -> store "ubuntu-26.04" (Ubuntu 26.04 LTS VM)

`load_all_runbooks()` with no argument reads the store named by the
`RUNBOOK_STORE` environment variable, defaulting to "default", so the engine
and the live demo keep their current behaviour until the team flips the switch.
"""
import os
import json
import re
from typing import Optional

import yaml

RUNBOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "runbooks")
UBUNTU_STORE = "ubuntu-26.04"
DEFAULT_STORE = "default"

# --- Cache: avoid re-reading + re-parsing YAML from disk on every incident ---
_cached_runbooks: dict[str, list[dict]] = {}
_cache_mtime: dict[str, float] = {}


def active_store() -> str:
    """Store the engine reads when no store is passed explicitly."""
    return os.environ.get("RUNBOOK_STORE", DEFAULT_STORE)


def store_dir(store: Optional[str] = None) -> str:
    """Filesystem directory backing a store.

    The default store stays on module-level `RUNBOOKS_DIR` so tests that
    monkeypatch that constant keep working.
    """
    store = store or active_store()
    if store == DEFAULT_STORE:
        return RUNBOOKS_DIR
    return os.path.join(RUNBOOKS_DIR, store)


def clear_cache(store: Optional[str] = None) -> None:
    """Drop cached runbooks for one store, or for all of them."""
    if store is None:
        _cached_runbooks.clear()
        _cache_mtime.clear()
    else:
        _cached_runbooks.pop(store, None)
        _cache_mtime.pop(store, None)


def load_runbook(yaml_path: str) -> dict:
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


def _yaml_files(directory: str) -> list[str]:
    """YAML files directly inside `directory` — sub-stores are not recursed."""
    if not os.path.exists(directory):
        return []
    return sorted(
        os.path.join(directory, f)
        for f in os.listdir(directory)
        if f.endswith((".yaml", ".yml"))
    )


def _latest_mtime(directory: str) -> float:
    return max((os.path.getmtime(p) for p in _yaml_files(directory)), default=0.0)


def resolve_parameters(rb: dict) -> dict:
    """Substitute `{name}` placeholders with the parameter defaults.

    Schema v1.1 lets a runbook declare `parameters` so one runbook covers a
    family of incidents (which sink, which connector, which block device)
    instead of hard-coding one machine's values. Executors receive commands
    that are already concrete, so no engine change is needed; the declared
    parameters stay on the runbook for the UI to override later.
    """
    params = rb.get("parameters") or []
    if not params:
        return rb

    defaults = {p["name"]: str(p.get("default", "")) for p in params}

    def fill(command: str) -> str:
        for name, value in defaults.items():
            command = command.replace("{" + name + "}", value)
        return command

    resolved = dict(rb)
    for section in ("pre_checks", "remediation_steps", "verification", "rollback_plan"):
        if rb.get(section):
            resolved[section] = [
                {**item, "command": fill(item.get("command", ""))} for item in rb[section]
            ]
    return resolved


def load_all_runbooks(store: Optional[str] = None) -> list[dict]:
    """Load (and cache) every runbook in a store, with parameters resolved.

    The first call reads and parses every YAML file. Subsequent calls reuse
    the cached list until a runbook file changes on disk. This removes a
    repeated disk-I/O + parse cost per incident (the matcher calls this on
    every incident).
    """
    store = store or active_store()
    directory = store_dir(store)

    cached = _cached_runbooks.get(store)
    if cached is not None and _latest_mtime(directory) <= _cache_mtime.get(store, 0.0):
        return cached

    runbooks = [resolve_parameters(load_runbook(p)) for p in _yaml_files(directory)]

    _cached_runbooks[store] = runbooks
    _cache_mtime[store] = _latest_mtime(directory)
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


def seed_runbooks_db(store: Optional[str] = None) -> int:
    """Sync the YAML runbooks of a store into the SQLite `runbooks` table.

    The engine matches against the YAML store; this keeps the database view
    (exposed via GET /api/runbooks) consistent with it. Idempotent
    (INSERT OR REPLACE). Returns the number of runbooks seeded.
    """
    from ..database import insert_runbook, prune_runbooks_not_in

    runbooks = load_all_runbooks(store)
    for rb in runbooks:
        insert_runbook(runbook_to_db_format(rb))

    # The database persists across restarts, so switching stores would
    # otherwise leave the previous platform's runbooks on display in
    # GET /api/runbooks while the engine matches only this store.
    prune_runbooks_not_in([rb.get("runbook_id", "") for rb in runbooks])
    return len(runbooks)
