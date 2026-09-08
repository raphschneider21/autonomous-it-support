import json
from datetime import datetime


def generate_escalation_ticket(incident: dict, audit_entries: list[dict]) -> dict:
    attempted = []
    for entry in audit_entries:
        if entry.get("action_type") in ("remediation", "diagnosis"):
            attempted.append({
                "action": entry.get("command_executed", "N/A"),
                "result": "Success" if entry.get("output") else "No output",
                "verification_outcome": entry.get("output", ""),
            })

    return {
        "ticket_title": f"Escalation: {incident.get('category', 'Unknown')} issue on {incident.get('hostname', 'Unknown')}",
        "priority": "P3 - Moderate",
        "requester": {
            "username": "endpoint-user",
            "department": "unknown",
        },
        "device_telemetry": {
            "hostname": incident.get("hostname", "Unknown"),
            "os_version": incident.get("os_version", "Unknown"),
        },
        "issue_context": {
            "user_reported_symptom": incident.get("user_prompt", ""),
            "attempted_remediations": attempted,
            "agent_assessment": incident.get("resolution_summary", "Unable to resolve. Requires Tier 2 specialist."),
        },
    }
