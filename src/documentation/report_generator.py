from datetime import datetime


def generate_report(incident: dict, audit_entries: list[dict]) -> str:
    timestamp = incident.get("created_at", datetime.utcnow().isoformat())
    inc_id = incident.get("id", "UNKNOWN")
    hostname = incident.get("hostname", "Unknown Host")
    user_prompt = incident.get("user_prompt", "N/A")

    lines = [
        f"# Incident Resolution Report: {inc_id}",
        f"- **Timestamp**: {timestamp}",
        f"- **Host / User**: {hostname}",
        f"- **Initial User Prompt**: \"{user_prompt}\"",
        "",
        "## 1. Root Cause Summary",
        incident.get("resolution_summary", "Under investigation."),
        "",
        "## 2. Actions Taken by Agent",
    ]

    for entry in audit_entries:
        ts = entry.get("timestamp", "")
        tier = entry.get("safety_tier", "green").upper()
        action = entry.get("action_type", "unknown")
        cmd = entry.get("command_executed", "N/A")
        output = entry.get("output", "")
        lines.append(f"- [{ts}] [{tier}] {action}: `{cmd}` — {output}")

    lines.extend([
        "",
        "## 3. Verification & Outcome",
        f"- **Final Status**: {incident.get('status', 'unknown').upper()}",
        f"- **Runbook Linked**: {incident.get('runbook_id') or 'None (New Case)'}",
    ])

    return "\n".join(lines)
