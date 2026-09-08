import json
from datetime import datetime
from ..models import IncidentStatus, SafetyTier
from ..database import insert_incident, update_incident, get_incident, insert_audit
from .triage_agent import classify_from_mock
from .diagnostic_agent import diagnose
from .security_agent import check_action, detect_prompt_injection
from ..knowledge.runbook_matcher import match_runbook
from ..integrations.escalation import generate_escalation_ticket
from ..documentation.report_generator import generate_report
from ..executors.mock_executor import MockExecutor

executor = MockExecutor()


def run_incident(incident_id: str, user_prompt: str) -> dict:
    insert_incident(incident_id, user_prompt)
    events = []

    # Step 1: Security check
    if detect_prompt_injection(user_prompt):
        _log(incident_id, "SecurityAgent", "blocked", "red", None, "Prompt injection detected")
        events.append({"agent": "SecurityAgent", "message": "ALERT: Prompt injection attempt detected and blocked.", "tier": "red"})
        update_incident(incident_id, status="escalated", resolution_summary="Prompt injection detected. Incident escalated.")
        return {"status": "escalated", "events": events, "runbook_id": None}

    _log(incident_id, "SecurityAgent", "input_check", "green", None, "No injection detected")
    events.append({"agent": "SecurityAgent", "message": "Input security check passed.", "tier": "green"})

    # Step 2: Triage
    update_incident(incident_id, status="diagnosing")
    classification = classify_from_mock(user_prompt)
    update_incident(incident_id, category=classification["category"], severity=classification["severity"])
    _log(incident_id, "TriageAgent", "classification", "green", None, json.dumps(classification))
    events.append({"agent": "TriageAgent", "message": f"Classified as {classification['category']} ({classification['severity']} severity).", "tier": "green"})

    # Step 3: Diagnostic
    diagnostics = diagnose(classification["category"], executor)
    for d in diagnostics:
        _log(incident_id, "DiagnosticAgent", "diagnosis", d["safety_tier"], d["command"], d["stdout"])
        events.append({"agent": "DiagnosticAgent", "message": f"Ran: {d['command']}", "tier": d["safety_tier"]})

    # Step 4: Runbook match
    runbook = match_runbook(user_prompt)
    if runbook:
        events.append({"agent": "IncidentCommander", "message": f"Runbook found: {runbook['title']}", "tier": "green"})

        # Execute remediation steps
        steps = runbook.get("remediation_steps", [])
        for step in steps:
            cmd = step.get("command", "")
            approval = check_action(cmd)

            if not approval["allowed"]:
                _log(incident_id, "SecurityAgent", "blocked", "red", cmd, approval["reason"])
                events.append({"agent": "SecurityAgent", "message": f"BLOCKED: {cmd} — {approval['reason']}", "tier": "red"})
                continue

            if approval.get("requires_approval"):
                _log(incident_id, "IncidentCommander", "awaiting_approval", "yellow", cmd, approval["reason"])
                events.append({"agent": "IncidentCommander", "message": f"Awaiting approval: {step.get('description', cmd)}", "tier": "yellow", "awaiting": True, "command": cmd})
                update_incident(incident_id, status="awaiting_approval")
                return {"status": "awaiting_approval", "events": events, "runbook_id": runbook.get("runbook_id"), "pending_command": cmd}

            output = executor.run(cmd)
            _log(incident_id, "DiagnosticAgent", "remediation", "yellow", cmd, output["stdout"])
            events.append({"agent": "DiagnosticAgent", "message": f"Executed: {cmd}", "tier": "yellow"})

        update_incident(incident_id, status="resolved", resolution_summary=f"Resolved via runbook {runbook.get('runbook_id')}", runbook_id=runbook.get("runbook_id"))
        events.append({"agent": "IncidentCommander", "message": "Incident resolved successfully.", "tier": "green"})
        return {"status": "resolved", "events": events, "runbook_id": runbook.get("runbook_id")}

    # No runbook found - escalate
    incident = get_incident(incident_id)
    ticket = generate_escalation_ticket(incident, get_audit(incident_id))
    update_incident(incident_id, status="escalated", resolution_summary="No matching runbook found. Escalated to Tier 2.")
    _log(incident_id, "IncidentCommander", "escalation", "yellow", None, json.dumps(ticket))
    events.append({"agent": "IncidentCommander", "message": "No runbook matched. Escalating to Tier 2 human support.", "tier": "yellow"})
    return {"status": "escalated", "events": events, "runbook_id": None, "escalation_ticket": ticket}


def approve_action(incident_id: str, command: str) -> dict:
    output = executor.run(command)
    _log(incident_id, "DiagnosticAgent", "remediation", "yellow", command, output["stdout"])

    incident = get_incident(incident_id)
    update_incident(incident_id, status="resolved", resolution_summary=f"Approved and executed: {command}")

    events = [
        {"agent": "DiagnosticAgent", "message": f"Executed approved command: {command}", "tier": "yellow"},
        {"agent": "IncidentCommander", "message": "Incident resolved after approved remediation.", "tier": "green"},
    ]
    return {"status": "resolved", "events": events}


def _log(incident_id, agent_name, action_type, safety_tier, command, output):
    insert_audit({
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat(),
        "agent_name": agent_name,
        "action_type": action_type,
        "safety_tier": safety_tier,
        "command_executed": command,
        "output": output,
    })


def get_audit(incident_id):
    from ..database import get_audit_log
    return get_audit_log(incident_id)
