import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.integrations.escalation import generate_escalation_ticket
from src.models import EscalationTicket


def test_generate_escalation_ticket_validates():
    incident = {
        "id": "INC-123",
        "user_prompt": "VPN won't connect",
        "category": "network",
        "hostname": "ws-abc",
        "os_version": "Windows 11",
        "resolution_summary": "No matching runbook.",
    }
    audit = [
        {"action_type": "remediation", "command_executed": "Restart-Service -Name rasman", "output": "ok"},
        {"action_type": "diagnosis", "command_executed": "Get-NetAdapter", "output": ""},
        {"action_type": "security_check", "command_executed": None, "output": None},
    ]

    ticket = generate_escalation_ticket(incident, audit)

    assert isinstance(ticket, EscalationTicket)
    data = ticket.model_dump()
    assert data["incident_id"] == "INC-123"
    assert data["requester"]["username"] == "endpoint-user"
    assert data["device_telemetry"]["hostname"] == "ws-abc"
    assert data["issue_context"]["user_reported_symptom"] == "VPN won't connect"
    assert len(data["issue_context"]["attempted_remediations"]) == 2

    # Re-parse the dumped dict to prove it round-trips against the schema.
    reparsed = EscalationTicket.model_validate(data)
    assert reparsed == ticket


def test_empty_audit_produces_no_remediations():
    incident = {"id": "INC-9", "user_prompt": "x", "category": "printer"}
    ticket = generate_escalation_ticket(incident, [])
    assert ticket.issue_context.attempted_remediations == []
