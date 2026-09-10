"""Service Desk: documentation fields, derived ownership, and the trace.

The claims this file protects are the ones the demo makes out loud. "A
`still_broken` verdict moves the ticket to HUMAN L2" is asserted here rather
than checked by eye on a projector, and the same goes for the refusal path and
for documentation surviving a later partial snapshot.
"""
import json
import pathlib

import pytest
from fastapi.testclient import TestClient

from src.monitoring import presentation, store
from src.monitoring.app import app

FIXTURES = pathlib.Path(__file__).parent / "fixtures" / "service_desk"


@pytest.fixture(autouse=True)
def _isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "DB_PATH", str(tmp_path / "tickets.db"))
    store.init_db()


@pytest.fixture
def desk():
    with TestClient(app) as client:
        yield client


def scenario(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


# --- Backward compatibility ------------------------------------------------

def test_a_ticket_without_the_new_fields_still_ingests(desk):
    """Dev1's client does not send documentation yet. That must stay fine."""
    body = desk.post("/api/tickets", json={
        "incident_id": "INC-OLD", "status": "open", "user_prompt": "printer broken",
    })
    assert body.status_code == 200
    ticket = body.json()
    assert ticket["incident_report"] is None
    assert ticket["runbook"] is None
    assert ticket["support_level"] == presentation.AUTOMATED_L1


def test_the_minimum_payload_is_just_an_incident_id(desk):
    assert desk.post("/api/tickets", json={"incident_id": "INC-MIN"}).status_code == 200


def test_repeated_reports_update_rather_than_duplicate(desk):
    desk.post("/api/tickets", json={"incident_id": "INC-1", "status": "open"})
    desk.post("/api/tickets", json={"incident_id": "INC-1", "status": "escalated"})
    assert len(desk.get("/api/tickets").json()) == 1
    assert desk.get("/api/tickets/INC-1").json()["status"] == "escalated"


# --- Optional documentation ------------------------------------------------

def test_incident_report_and_runbook_persist(desk):
    desk.post("/api/tickets", json={
        "incident_id": "INC-DOC", "status": "open",
        "incident_report": "# Incident Report\n\nCUPS was inactive.",
        "runbook": {"runbook_id": "RB-CUPS-001", "title": "Print Queue Stuck",
                    "steps": [{"command": "sudo systemctl restart cups"}]},
    })
    ticket = desk.get("/api/tickets/INC-DOC").json()
    assert "CUPS was inactive" in ticket["incident_report"]
    assert ticket["runbook"]["runbook_id"] == "RB-CUPS-001"
    assert ticket["runbook"]["steps"][0]["command"] == "sudo systemctl restart cups"


def test_a_later_snapshot_without_documentation_does_not_erase_it(desk):
    """Documentation arrives late and is not repeated on every update."""
    desk.post("/api/tickets", json={
        "incident_id": "INC-DOC2", "status": "open",
        "incident_report": "the report", "runbook": {"runbook_id": "RB-X"},
    })
    desk.post("/api/tickets", json={"incident_id": "INC-DOC2", "status": "closed"})

    ticket = desk.get("/api/tickets/INC-DOC2").json()
    assert ticket["incident_report"] == "the report"
    assert ticket["runbook"]["runbook_id"] == "RB-X"


def test_documentation_absent_does_not_break_stats(desk):
    desk.post("/api/tickets", json={"incident_id": "INC-NO-DOC", "status": "open"})
    assert desk.get("/api/stats").json()["total"] == 1


# --- Ownership: the claim the demo makes out loud --------------------------

@pytest.mark.parametrize("status,expected", [
    ("open", presentation.AUTOMATED_L1),
    ("diagnosing", presentation.AUTOMATED_L1),
    ("closed", presentation.AUTOMATED_L1),
    ("escalated", presentation.HUMAN_L2),
])
def test_support_ownership_is_derived_from_status(status, expected):
    assert presentation.support_level(status) == expected


def test_still_broken_moves_the_ticket_to_a_human(desk):
    """The core business moment of Scenario B."""
    desk.post("/api/tickets", json=scenario("scenario_b_still_broken"))
    ticket = desk.get("/api/tickets/INC-B31902F1").json()

    assert ticket["support_level"] == presentation.HUMAN_L2
    assert ticket["display_status"] == "ESCALATED"
    assert ticket["false_resolution"] is True
    assert "still present" in ticket["escalation_reason"]


def test_a_solved_confirmation_keeps_the_ticket_with_automation(desk):
    desk.post("/api/tickets", json=scenario("scenario_a_cups_resolved"))
    ticket = desk.get("/api/tickets/INC-A82F91D3").json()
    assert ticket["support_level"] == presentation.AUTOMATED_L1
    assert ticket["display_status"] == "CLOSED"
    assert ticket["false_resolution"] is False


def test_verified_but_unconfirmed_reads_as_awaiting_the_user():
    """`open` means two different things; the UI must not call both of them open."""
    assert presentation.display_status("open", None) == "INVESTIGATING"
    assert presentation.display_status("open", "solved") == "AWAITING USER"


def test_false_resolution_requires_an_actual_verification_step():
    """Without a verification in the audit trail there is nothing to contradict."""
    assert not presentation.is_false_resolution(
        {"user_confirmed": "still_broken", "actions": []})
    assert presentation.is_false_resolution(
        {"user_confirmed": "still_broken", "actions": [{"action": "verification"}]})


# --- Refusal ---------------------------------------------------------------

def test_a_refused_incident_is_flagged_and_explains_itself(desk):
    desk.post("/api/tickets", json=scenario("scenario_c_refusal"))
    ticket = desk.get("/api/tickets/INC-C281AD72").json()

    assert ticket["refused"] is True
    assert ticket["support_level"] == presentation.HUMAN_L2
    assert "No remediation" in ticket["escalation_reason"]


def test_refusal_actions_survive_storage_and_hydration(desk):
    desk.post("/api/tickets", json=scenario("scenario_c_refusal"))
    ticket = desk.get("/api/tickets/INC-C281AD72").json()
    assert any(a["tier"] == "red" for a in ticket["actions"])
    assert ticket["errors"], "the refusal was not preserved as an error"


# --- Trace and timeline ----------------------------------------------------

def test_the_trace_relabels_real_audit_entries():
    ticket = scenario("scenario_a_cups_resolved")
    components = [row["component"] for row in presentation.trace(ticket)]
    assert components[0] == "SECURITY"
    assert "TRIAGE" in components and "DIAGNOSTIC" in components
    assert "EXECUTOR" in components and "VERIFY" in components


def test_the_trace_never_invents_rows():
    """One trace row per reported audit entry, minus deliberately hidden noise."""
    ticket = scenario("scenario_a_cups_resolved")
    visible = [a for a in ticket["actions"]
               if a["action"] not in presentation.TRACE_HIDDEN_ACTIONS]
    assert len(presentation.trace(ticket)) == len(visible)


def test_a_refused_command_is_marked_in_the_trace():
    rows = presentation.trace(scenario("scenario_c_refusal"))
    assert any(row["refused"] for row in rows)
    assert any(row["component"] == "REFUSED" for row in rows)


def test_the_timeline_labels_inferred_stages_as_inferred():
    """A stage derived from ticket state must not pose as recorded evidence."""
    stages = presentation.timeline(scenario("scenario_a_cups_resolved"))
    by_stage = {s["stage"]: s for s in stages}

    assert by_stage["Security policy check"]["source"] == "recorded"
    assert by_stage["Employee confirmation"]["source"] == "inferred"
    assert by_stage["Runbook applied"]["source"] == "inferred"


def test_the_timeline_omits_stages_with_no_evidence():
    """Scenario C never reaches diagnostics; the timeline must not pretend it did."""
    stages = {s["stage"] for s in presentation.timeline(scenario("scenario_c_refusal"))}
    assert "Diagnostics" not in stages
    assert "Remediation" not in stages


def test_the_timeline_is_empty_rather_than_fabricated_for_a_bare_ticket():
    assert presentation.timeline({"actions": []}) == []


# --- All three canonical scenarios round-trip ------------------------------

@pytest.mark.parametrize("name,incident_id,owner,state", [
    ("scenario_a_cups_resolved", "INC-A82F91D3", presentation.AUTOMATED_L1, "CLOSED"),
    ("scenario_b_still_broken", "INC-B31902F1", presentation.HUMAN_L2, "ESCALATED"),
    ("scenario_c_refusal", "INC-C281AD72", presentation.HUMAN_L2, "ESCALATED"),
])
def test_canonical_scenarios_render(desk, name, incident_id, owner, state):
    assert desk.post("/api/tickets", json=scenario(name)).status_code == 200
    ticket = desk.get(f"/api/tickets/{incident_id}").json()
    assert ticket["support_level"] == owner
    assert ticket["display_status"] == state
    assert ticket["actions"], "no agent activity to show"


# --- A live incident, reported progressively --------------------------------
# Dev1 commits to "early and repeated ticket snapshots for active incidents"
# (workstream contract §12). Everything above tests a finished ticket; this is
# the path the audience actually watches, where the ticket appears first and
# fills in afterwards.

def snapshot(incident_id, status, actions, **extra):
    payload = {
        "incident_id": incident_id, "hostname": "ubuntu-demo-01",
        "title": "Print jobs are stuck in the queue",
        "user_prompt": "Print jobs are stuck in the queue", "status": status,
        "actions": actions, "errors": [],
    }
    payload.update(extra)
    return payload


def action(kind, command=None, tier="green", output="", ts="2026-09-10T09:42:11"):
    return {"timestamp": ts, "agent": "DiagnosticAgent", "action": kind,
            "tier": tier, "command": command, "output": output}


def test_a_progressing_incident_grows_in_place(desk):
    """Three snapshots for one incident produce one ticket that accumulates."""
    desk.post("/api/tickets", json=snapshot("INC-LIVE", "diagnosing", [
        action("input_check", output="No injection detected")]))
    first = desk.get("/api/tickets/INC-LIVE").json()
    assert first["display_status"] == "INVESTIGATING"
    assert first["support_level"] == presentation.AUTOMATED_L1
    assert len(first["actions"]) == 1

    desk.post("/api/tickets", json=snapshot("INC-LIVE", "diagnosing", [
        action("input_check", output="No injection detected"),
        action("classification", output='{"category": "printing"}'),
        action("diagnosis", command="systemctl is-active cups", output="inactive")]))

    desk.post("/api/tickets", json=snapshot("INC-LIVE", "resolved", [
        action("input_check", output="No injection detected"),
        action("classification", output='{"category": "printing"}'),
        action("diagnosis", command="systemctl is-active cups", output="inactive"),
        action("remediation", command="sudo systemctl restart cups", tier="yellow"),
        action("verification", command="systemctl is-active cups", output="active")],
        runbook_id="RB-CUPS-001", category="printing"))

    assert len(desk.get("/api/tickets").json()) == 1, "snapshots created duplicate tickets"
    final = desk.get("/api/tickets/INC-LIVE").json()
    assert len(final["actions"]) == 5
    assert final["runbook_id"] == "RB-CUPS-001"


def test_the_trace_key_changes_only_when_the_trace_does(desk):
    """The browser re-renders on (incident, row count, status). Those must move.

    Without this the trace either freezes mid-incident or repaints on every
    poll and flickers while someone is reading it.
    """
    def key():
        t = desk.get("/api/tickets/INC-KEY").json()
        rows = presentation.trace(t)
        return f"{t['incident_id']}:{len(rows)}:{t['display_status']}"

    desk.post("/api/tickets", json=snapshot("INC-KEY", "diagnosing", [action("input_check")]))
    k1 = key()

    # Same snapshot again: nothing changed, so the key must not move.
    desk.post("/api/tickets", json=snapshot("INC-KEY", "diagnosing", [action("input_check")]))
    assert key() == k1, "an unchanged snapshot would have repainted the trace"

    # A new action must move it.
    desk.post("/api/tickets", json=snapshot("INC-KEY", "diagnosing",
        [action("input_check"), action("diagnosis", command="df -h /")]))
    k2 = key()
    assert k2 != k1

    # A status change with no new action must also move it.
    desk.post("/api/tickets", json=snapshot("INC-KEY", "escalated",
        [action("input_check"), action("diagnosis", command="df -h /")]))
    assert key() != k2, "a status change would not have repainted the trace"


def test_ownership_flips_on_the_final_snapshot(desk):
    """The L1 → L2 moment, arriving as an update to an existing ticket."""
    desk.post("/api/tickets", json=snapshot("INC-FLIP", "resolved", [
        action("verification", command="systemctl is-active cups", output="active")]))
    assert desk.get("/api/tickets/INC-FLIP").json()["support_level"] == presentation.AUTOMATED_L1

    desk.post("/api/tickets", json=snapshot("INC-FLIP", "escalated", [
        action("verification", command="systemctl is-active cups", output="active")],
        user_confirmed="still_broken"))

    flipped = desk.get("/api/tickets/INC-FLIP").json()
    assert flipped["support_level"] == presentation.HUMAN_L2
    assert flipped["false_resolution"] is True


def test_a_partial_ticket_still_renders_every_tab(desk):
    """A ticket reported early has no runbook, no report, no escalation."""
    desk.post("/api/tickets", json=snapshot("INC-BARE", "diagnosing", [action("input_check")]))
    t = desk.get("/api/tickets/INC-BARE").json()

    assert t["runbook"] is None and t["runbook_id"] is None
    assert t["incident_report"] is None
    assert t["escalation"] is None
    assert t["escalation_reason"] == ""
    assert presentation.timeline(t), "timeline should still show what was recorded"
    assert presentation.trace(t), "trace should still show what was recorded"


# --- Empty and degraded states ---------------------------------------------

def test_an_empty_service_desk_is_a_valid_state(desk):
    assert desk.get("/api/tickets").json() == []
    stats = desk.get("/api/stats").json()
    assert stats["total"] == 0
    assert stats["auto_resolution_rate"] == 0.0
    assert stats["false_resolution_rate"] == 0.0


def test_a_ticket_with_no_activity_at_all_does_not_crash_the_views(desk):
    desk.post("/api/tickets", json={"incident_id": "INC-VOID"})
    t = desk.get("/api/tickets/INC-VOID").json()
    assert presentation.trace(t) == []
    assert presentation.timeline(t) == []
    assert t["display_status"] == "INVESTIGATING"


def test_malformed_action_entries_do_not_break_derivation():
    """Defensive: the endpoint is another team's code and may change shape."""
    ticket = {"status": "open", "actions": [{}, {"action": None}, {"tier": "red"}]}
    assert presentation.was_refused(ticket) is True
    assert presentation.trace(ticket)
    assert presentation.presentation(ticket)["support_level"] == presentation.AUTOMATED_L1
