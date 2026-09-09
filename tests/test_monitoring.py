"""Monitoring service, ticket lifecycle, and the reporting path.

The property this file exists to protect: **a monitoring outage must never stop
a user's machine from being fixed.** Everything else here is lifecycle detail.
"""
import tempfile

import pytest
from fastapi.testclient import TestClient

import src.database as db
from src.integrations import monitoring_client
from src.monitoring import store
from src.monitoring.app import app as monitoring_app


@pytest.fixture(autouse=True)
def isolated_stores(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "tickets.db"))
    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "incidents.db"))
    store.init_db()
    db.init_db()
    monitoring_client._last_error = None


@pytest.fixture
def desk():
    with TestClient(monitoring_app) as client:
        yield client


def _report(desk, **overrides):
    payload = {
        "incident_id": "INC-0001",
        "hostname": "ubuntu-vm",
        "user_prompt": "Print jobs are stuck in the queue",
        "status": "open",
        "category": "printing",
    }
    payload.update(overrides)
    response = desk.post("/api/tickets", json=payload)
    assert response.status_code == 200, response.text
    return response.json()


# --- Ingestion ------------------------------------------------------------

def test_a_ticket_is_created_from_an_agent_report(desk):
    ticket = _report(desk)
    assert ticket["incident_id"] == "INC-0001"
    assert ticket["status"] == "open"
    assert ticket["hostname"] == "ubuntu-vm"


def test_reporting_the_same_incident_updates_rather_than_duplicates(desk):
    _report(desk)
    _report(desk, status="escalated", resolution="No runbook matched")

    assert len(desk.get("/api/tickets").json()) == 1
    ticket = desk.get("/api/tickets/INC-0001").json()
    assert ticket["status"] == "escalated"
    assert ticket["resolution"] == "No runbook matched"


def test_created_at_survives_updates(desk):
    first = _report(desk)
    second = _report(desk, status="escalated")
    assert second["created_at"] == first["created_at"]
    assert second["updated_at"] >= first["updated_at"]


def test_a_verified_fix_is_not_closed_until_the_user_confirms(desk):
    """The agent's "resolved" is not the service desk's "closed"."""
    ticket = _report(desk, status="resolved")
    assert ticket["status"] == "open", "a technical pass must not close a ticket"

    ticket = _report(desk, status="resolved", user_confirmed="solved")
    assert ticket["status"] == "closed"


def test_unknown_status_is_rejected(desk):
    response = desk.post("/api/tickets", json={"incident_id": "X", "status": "vibes"})
    assert response.status_code == 422


def test_missing_incident_id_is_rejected(desk):
    assert desk.post("/api/tickets", json={"status": "open"}).status_code == 422


# --- Listing and filtering ------------------------------------------------

def test_tickets_filter_by_state(desk):
    _report(desk, incident_id="INC-A", status="open")
    _report(desk, incident_id="INC-B", status="escalated")
    _report(desk, incident_id="INC-C", status="resolved", user_confirmed="solved")

    assert {t["incident_id"] for t in desk.get("/api/tickets?status=open").json()} == {"INC-A"}
    assert {t["incident_id"] for t in desk.get("/api/tickets?status=escalated").json()} == {"INC-B"}
    assert {t["incident_id"] for t in desk.get("/api/tickets?status=closed").json()} == {"INC-C"}
    assert len(desk.get("/api/tickets").json()) == 3


def test_unknown_ticket_is_404(desk):
    assert desk.get("/api/tickets/INC-NOPE").status_code == 404


# --- Stats ----------------------------------------------------------------

def test_false_resolution_rate_is_measured(desk):
    """The number a technical check cannot produce on its own."""
    _report(desk, incident_id="INC-A", status="resolved", user_confirmed="solved")
    _report(desk, incident_id="INC-B", status="resolved", user_confirmed="solved")
    _report(desk, incident_id="INC-C", status="escalated", user_confirmed="still_broken")

    stats = desk.get("/api/stats").json()
    assert stats["confirmations"] == 3
    assert stats["false_resolution_rate"] == pytest.approx(1 / 3, abs=0.01)


def test_stats_are_safe_with_no_tickets(desk):
    stats = desk.get("/api/stats").json()
    assert stats["total"] == 0
    assert stats["false_resolution_rate"] == 0.0


# --- The reporting client -------------------------------------------------

def test_report_returns_false_when_the_service_desk_is_down(monkeypatch):
    monkeypatch.setenv("MONITORING_URL", "http://127.0.0.1:9")  # discard port
    assert monitoring_client.report({"incident_id": "INC-X"}) is False
    assert "unreachable" in monitoring_client.last_error()


def test_report_never_raises_whatever_goes_wrong(monkeypatch):
    def explode(*a, **kw):
        raise RuntimeError("network on fire")

    monkeypatch.setattr(monitoring_client.urllib.request, "urlopen", explode)
    assert monitoring_client.report({"incident_id": "INC-X"}) is False


def test_reporting_can_be_disabled(monkeypatch):
    monkeypatch.setenv("MONITORING_ENABLED", "0")
    assert monitoring_client.report({"incident_id": "INC-X"}) is False
    assert monitoring_client.last_error() == "disabled"


def test_monitoring_url_defaults_to_localhost(monkeypatch):
    monkeypatch.delenv("MONITORING_URL", raising=False)
    assert monitoring_client.monitoring_url() == "http://127.0.0.1:8001"


def test_monitoring_url_is_configurable_for_a_second_machine(monkeypatch):
    monkeypatch.setenv("MONITORING_URL", "http://10.211.55.2:8001/")
    assert monitoring_client.monitoring_url() == "http://10.211.55.2:8001"


def test_build_report_separates_refusals_from_ordinary_activity():
    incident = {"id": "INC-1", "user_prompt": "wifi keeps dropping", "category": "network"}
    audit = [
        {"agent_name": "DiagnosticAgent", "action_type": "diagnosis",
         "safety_tier": "green", "command_executed": "rfkill list", "output": "ok"},
        {"agent_name": "SecurityAgent", "action_type": "blocked",
         "safety_tier": "red", "command_executed": "useradd evil", "output": "denied"},
    ]
    report = monitoring_client.build_report(incident, audit, {"status": "escalated"})

    assert len(report["actions"]) == 2
    assert len(report["errors"]) == 1
    assert report["errors"][0]["command"] == "useradd evil"


# --- The property that matters --------------------------------------------

def test_a_dead_service_desk_does_not_stop_the_fix(monkeypatch):
    """The whole point of fire-and-forget reporting."""
    monkeypatch.setenv("MONITORING_URL", "http://127.0.0.1:9")
    monkeypatch.setenv("RUNBOOK_STORE", "ubuntu-26.04")

    from src.engine.incident_commander import run_incident

    result = run_incident("INC-OUTAGE", "Print jobs are stuck in the queue and I cannot delete them")

    assert result["status"] == "resolved", "a monitoring outage broke the remediation"
    assert result["runbook_id"] == "RB-CUPS-001"

    # ...and the failure to report is itself audited, so the gap is discoverable
    audit = db.get_audit_log("INC-OUTAGE")
    assert any(e["action_type"] == "monitoring_unreachable" for e in audit)
