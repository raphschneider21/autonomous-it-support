from src.models import (
    EscalationTicket,
    Requester,
    DeviceTelemetry,
    IssueContext,
    AttemptedRemediation,
)


def generate_escalation_ticket(incident: dict, audit_entries: list[dict]) -> EscalationTicket:
    """Build a typed Tier 2/3 escalation ticket from an incident and its audit trail."""
    attempted = []
    for entry in audit_entries:
        if entry.get("action_type") in ("remediation", "diagnosis"):
            attempted.append(AttemptedRemediation(
                action=entry.get("command_executed", "N/A"),
                result="Success" if entry.get("output") else "No output",
                verification_outcome=entry.get("output", ""),
            ))

    return EscalationTicket(
        ticket_title=f"Escalation: {incident.get('category', 'Unknown')} issue on {incident.get('hostname', 'Unknown')}",
        requester=Requester(
            username="endpoint-user",
            department="unknown",
        ),
        device_telemetry=DeviceTelemetry(
            hostname=incident.get("hostname", "Unknown"),
            os_version=incident.get("os_version", "Unknown"),
        ),
        issue_context=IssueContext(
            user_reported_symptom=incident.get("user_prompt", ""),
            attempted_remediations=attempted,
            agent_assessment=incident.get(
                "resolution_summary",
                "Unable to resolve. Requires Tier 2 specialist.",
            ),
        ),
        incident_id=incident.get("id", ""),
    )
