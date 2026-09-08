import yaml
import os
import json
from typing import Optional

RUNBOOKS_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "runbooks")


def load_runbook(yaml_path: str) -> dict:
    with open(yaml_path, "r") as f:
        return yaml.safe_load(f)


def load_all_runbooks() -> list[dict]:
    runbooks = []
    if not os.path.exists(RUNBOOKS_DIR):
        return runbooks
    for filename in os.listdir(RUNBOOKS_DIR):
        if filename.endswith((".yaml", ".yml")):
            path = os.path.join(RUNBOOKS_DIR, filename)
            runbooks.append(load_runbook(path))
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
