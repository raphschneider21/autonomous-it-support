import sys
import os
import tempfile
import uuid

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.engine.incident_commander import run_incident
import src.database as db


def _fresh_db():
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    db.DB_PATH = tmp.name
    db.init_db()


def _cleanup_db():
    if os.path.exists(db.DB_PATH):
        os.unlink(db.DB_PATH)


def test_disagreement_surfaces_in_event_stream():
    _fresh_db()
    try:
        # Demo scenario from live-demo-spec: ERP down + strange prompt
        test_id = f"TEST-DISAGREE-{uuid.uuid4().hex[:6].upper()}"
        result = run_incident(test_id, "Our team cannot access the ERP; users report a strange prompt")
        messages = [e["message"] for e in result["events"]]
        assert any("Disagreement detected" in m for m in messages), messages
        assert any("security/credential_harvesting" in m for m in messages), messages
    finally:
        _cleanup_db()


def test_no_disagreement_for_benign_incident():
    _fresh_db()
    try:
        test_id = f"TEST-AGREE-{uuid.uuid4().hex[:6].upper()}"
        result = run_incident(test_id, "My printer is stuck and cannot print")
        messages = [e["message"] for e in result["events"]]
        assert any("agree on root cause" in m for m in messages), messages
        assert not any("Disagreement detected" in m for m in messages), messages
    finally:
        _cleanup_db()