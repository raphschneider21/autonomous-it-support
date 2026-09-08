import json
from datetime import datetime
from ..models import IncidentStatus, SafetyTier
from ..database import insert_incident, update_incident, get_incident, insert_audit
from .triage_agent import classify_from_mock
from .diagnostic_agent import diagnose
from .security_agent import check_action, detect_prompt_injection
from .event_stream import store
from ..knowledge.runbook_matcher import match_runbook
from ..integrations.escalation import generate_escalation_ticket
from ..documentation.report_generator import generate_report
from ..executors.mock_executor import MockExecutor

executor = MockExecutor()


def _emit(incident_id: str, event: dict):
    """Push a single event to the incident's live stream."""
    store.push(incident_id, event)


def run_incident(incident_id: str, user_prompt: str) -> dict:
    insert_incident(incident_id, user_prompt)

    # Step 1: Security check
    if detect_prompt_injection(user_prompt):
        _log(incident_id, "SecurityAgent", "blocked", "red", None, "Prompt injection detected")
        _emit(incident_id, {"agent": "SecurityAgent", "message": "ALERT: Prompt injection attempt detected and blocked.", "tier": "red"})
        update_incident(incident_id, status="escalated", resolution_summary="Prompt injection detected. Incident escalated.")
        result = {"status": "escalated", "runbook_id": None}
        store.set_result(incident_id, result)
        return result

    _log(incident_id, "SecurityAgent", "input_check", "green", None, "No injection detected")
    _emit(incident_id, {"agent": "SecurityAgent", "message": "Input security check passed.", "tier": "green"})

    # Step 2: Triage
    update_incident(incident_id, status="diagnosing")
    classification = classify_from_mock(user_prompt)
    update_incident(incident_id, category=classification["category"], severity=classification["severity"])
    _log(incident_id, "TriageAgent", "classification", "green", None, json.dumps(classification))
    _emit(incident_id, {"agent": "TriageAgent", "message": f"Classified as {classification['category']} ({classification['severity']} severity).", "tier": "green"})

    # Step 3: Diagnostic
    diagnostics = diagnose(classification["category"], executor)
    for d in diagnostics:
        _log(incident_id, "DiagnosticAgent", "diagnosis", d["safety_tier"], d["command"], d["stdout"])
        _emit(incident_id, {"agent": "DiagnosticAgent", "message": f"Ran: {d['command']}", "tier": d["safety_tier"]})

    # Step 4: Runbook match
    runbook = match_runbook(user_prompt)
    if runbook:
        _emit(incident_id, {"agent": "IncidentCommander", "message": f"Runbook found: {runbook['title']}", "tier": "green"})

        # Execute remediation steps
        steps = runbook.get("remediation_steps", [])
        for step in steps:
            cmd = step.get("command", "")
            approval = check_action(cmd)

            if not approval["allowed"]:
                _log(incident_id, "SecurityAgent", "blocked", "red", cmd, approval["reason"])
                _emit(incident_id, {"agent": "SecurityAgent", "message": f"BLOCKED: {cmd} — {approval['reason']}", "tier": "red"})
                continue

            if approval.get("requires_approval"):
                _log(incident_id, "IncidentCommander", "awaiting_approval", "yellow", cmd, approval["reason"])
                _emit(incident_id, {"agent": "IncidentCommander", "message": f"Awaiting approval: {step.get('description', cmd)}", "tier": "yellow", "awaiting": True, "command": cmd})
                update_incident(incident_id, status="awaiting_approval")
                result = {"status": "awaiting_approval", "runbook_id": runbook.get("runbook_id"), "pending_command": cmd}
                store.set_result(incident_id, result)
                return result

            output = executor.run(cmd)
            _log(incident_id, "DiagnosticAgent", "remediation", "yellow", cmd, output["stdout"])
            _emit(incident_id, {"agent": "DiagnosticAgent", "message": f"Executed: {cmd}", "tier": "yellow"})

        update_incident(incident_id, status="resolved", resolution_summary=f"Resolved via runbook {runbook.get('runbook_id')}", runbook_id=runbook.get("runbook_id"))
        _emit(incident_id, {"agent": "IncidentCommander", "message": "Incident resolved successfully.", "tier": "green"})
        result = {"status": "resolved", "runbook_id": runbook.get("runbook_id")}
        store.set_result(incident_id, result)
        return result

    # No runbook found - escalate
    incident = get_incident(incident_id)
    ticket = generate_escalation_ticket(incident, get_audit(incident_id))
    update_incident(incident_id, status="escalated", resolution_summary="No matching runbook found. Escalated to Tier 2.")
    _log(incident_id, "IncidentCommander", "escalation", "yellow", None, json.dumps(ticket))
    _emit(incident_id, {"agent": "IncidentCommander", "message": "No runbook matched. Escalating to Tier 2 human support.", "tier": "yellow"})
    result = {"status": "escalated", "runbook_id": None, "escalation_ticket": ticket}
    store.set_result(incident_id, result)
    return result


def approve_action(incident_id: str, command: str) -> dict:
    output = executor.run(command)
    _log(incident_id, "DiagnosticAgent", "remediation", "yellow", command, output["stdout"])

    incident = get_incident(incident_id)
    update_incident(incident_id, status="resolved", resolution_summary=f"Approved and executed: {command}")

    events = [
        {"agent": "DiagnosticAgent", "message": f"Executed approved command: {command}", "tier": "yellow"},
        {"agent": "IncidentCommander", "message": "Incident resolved after approved remediation.", "tier": "green"},
    ]
    for e in events:
        _emit(incident_id, e)

    result = {"status": "resolved", "events": events}
    store.set_result(incident_id, result)
    return result


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
