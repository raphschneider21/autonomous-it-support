import sys
import os
import tempfile
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.incident_commander import _run_verification, _finalize_runbook
from src.executors.factory import get_executor
import src.database as db


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db.DB_PATH = tmp.name
    db.init_db()


def _cleanup_db():
    if os.path.exists(db.DB_PATH):
        os.unlink(db.DB_PATH)


def test_verification_passes_when_regex_matches():
    _fresh_db()
    try:
        runbook = {"verification": [{"command": "echo running", "expected_output_regex": "run"}]}
        result = _run_verification("T-1", runbook, get_executor(), [])
        assert result["passed"] is True
        assert result["tool_calls"] == 1
    finally:
        _cleanup_db()


def test_verification_fails_when_regex_does_not_match():
    _fresh_db()
    try:
        runbook = {"verification": [{"command": "echo running", "expected_output_regex": "something_else"}]}
        result = _run_verification("T-2", runbook, get_executor(), [])
        assert result["passed"] is False
    finally:
        _cleanup_db()


def test_verification_passes_empty_spec():
    _fresh_db()
    try:
        runbook = {"verification": []}
        result = _run_verification("T-3", runbook, get_executor(), [])
        assert result["passed"] is True
    finally:
        _cleanup_db()


def test_failed_verification_escalates():
    _fresh_db()
    try:
        runbook = {
            "runbook_id": "RB-FAIL-001",
            "title": "Never Passing Runbook",
            "verification": [{"command": "echo whatever", "expected_output_regex": "NEVER_MATCHES"}],
        }
        incident_id = f"VERIFY-FAIL-{uuid.uuid4().hex[:6].upper()}"
        db.insert_incident(incident_id, "test prompt")
        result = _finalize_runbook(incident_id, runbook, [], 0.0, 0)
        assert result["status"] == "escalated"
        assert any("Verification failed" in e["message"] for e in result["events"])
        assert "escalation_ticket" in result
        incident = db.get_incident(incident_id)
        assert incident["status"] == "escalated"
    finally:
        _cleanup_db()