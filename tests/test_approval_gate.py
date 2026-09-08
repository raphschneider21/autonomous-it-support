import sys
import os
import tempfile
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.incident_commander import run_incident, approve_action
from src.database import init_db, get_incident, get_audit_log
import src.database as db


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db.DB_PATH = tmp.name
    init_db()


def _cleanup_db():
    if os.path.exists(db.DB_PATH):
        os.unlink(db.DB_PATH)


def _start_awaiting_incident(prompt: str) -> str:
    """Run an incident that reaches the approval gate and return its id."""
    test_id = f"TEST-APPROVE-{uuid.uuid4().hex[:6].upper()}"
    result = run_incident(test_id, prompt)
    assert result["status"] == "awaiting_approval"
    assert result.get("pending_command") is not None
    return test_id


def test_yellow_command_executes_on_approval():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        result = approve_action(incident_id, "Stop-Service -Name spooler -Force")
        assert result["status"] == "resolved"
        incident = get_incident(incident_id)
        assert incident["status"] == "resolved"
        audit = get_audit_log(incident_id)
        assert any(e["action_type"] == "approval" for e in audit)
        assert any(e["action_type"] == "remediation" for e in audit)
    finally:
        _cleanup_db()


def test_red_command_blocked_on_approval():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        result = approve_action(incident_id, "net user evil /add")
        assert result["status"] == "blocked"
        assert any("BLOCKED" in e["message"] for e in result["events"])
        # Command must NOT have executed
        audit = get_audit_log(incident_id)
        assert not any(e["action_type"] == "remediation" for e in audit)
        incident = get_incident(incident_id)
        assert incident["status"] != "resolved"
    finally:
        _cleanup_db()


def test_red_command_with_obfuscated_spacing_blocked():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        result = approve_action(incident_id, "net    user   evil   /add")
        assert result["status"] == "blocked"
    finally:
        _cleanup_db()


def test_approval_gate_logs_block_to_audit():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        approve_action(incident_id, "Remove-Item -Path C:\\Windows -Recurse -Force")
        audit = get_audit_log(incident_id)
        assert any(e["action_type"] == "blocked" and e["safety_tier"] == "red" for e in audit)
    finally:
        _cleanup_db()


def test_report_generated_on_approval_resolution():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        result = approve_action(incident_id, "Stop-Service -Name spooler -Force")
        assert result["status"] == "resolved"
        report_path = result.get("report_path")
        assert report_path and os.path.exists(report_path)
        with open(report_path) as f:
            content = f.read()
        assert "Incident Resolution Report" in content
        assert incident_id in content
        assert "RESOLVED" in content
    finally:
        _cleanup_db()


def test_report_generated_on_auto_resolve():
    _fresh_db()
    try:
        test_id = f"TEST-AUTORESOLVE-{uuid.uuid4().hex[:6].upper()}"
        result = run_incident(test_id, "Legacy application error 76 path not found")
        assert result["status"] == "resolved"
        report_path = result.get("report_path")
        assert report_path and os.path.exists(report_path)
        with open(report_path) as f:
            content = f.read()
        assert "Incident Resolution Report" in content
        assert test_id in content
    finally:
        _cleanup_db()


def test_approval_resumes_remaining_runbook_steps():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        result = approve_action(incident_id, "Stop-Service -Name spooler -Force")
        assert result["status"] == "resolved"
        executed = [e["message"] for e in result["events"] if "Executed" in e["message"]]
        # Approve step 1, then resume: delete files, start service
        assert any("Stop-Service" in m for m in executed)
        assert any("Remove-Item" in m for m in executed)
        assert any("Start-Service" in m for m in executed)
    finally:
        _cleanup_db()


def test_verification_runs_and_passes_on_resolve():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        result = approve_action(incident_id, "Stop-Service -Name spooler -Force")
        assert any("Verification PASSED" in e["message"] for e in result["events"])
        assert any("Verification passed" in e["message"] for e in result["events"])
    finally:
        _cleanup_db()


def test_metrics_recorded_in_audit():
    _fresh_db()
    try:
        incident_id = _start_awaiting_incident("Print jobs are stuck in the queue")
        approve_action(incident_id, "Stop-Service -Name spooler -Force")
        entries = get_audit_log(incident_id)
        metrics = [e for e in entries if e["action_type"] == "metrics"]
        assert metrics, "metrics entry should be logged"
        import json
        payload = json.loads(metrics[-1]["output"])
        assert payload["status"] == "resolved"
        assert payload["latency_ms"] >= 0
        assert payload["tool_calls"] >= 4
    finally:
        _cleanup_db()