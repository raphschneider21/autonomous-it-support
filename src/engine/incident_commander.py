import json
import os
import re
import time
from datetime import datetime
from ..models import IncidentStatus, SafetyTier
from ..database import insert_incident, update_incident, get_incident, insert_audit
from .triage_agent import classify_from_mock
from .diagnostic_agent import diagnose, assess as diagnostic_assess
from .security_agent import check_action, detect_prompt_injection, assess_prompt
from .disagreement import reconcile_assessments
from ..knowledge.runbook_matcher import match_runbook
from ..knowledge.runbook_parser import load_all_runbooks
from ..integrations.escalation import generate_escalation_ticket
from ..documentation.report_generator import generate_report
from ..executors.mock_executor import MockExecutor

executor = MockExecutor()


def run_incident(incident_id: str, user_prompt: str) -> dict:
    start = time.perf_counter()
    tool_calls = 0
    insert_incident(incident_id, user_prompt)
    events = []

    # Step 1: Security check
    if detect_prompt_injection(user_prompt):
        _log(incident_id, "SecurityAgent", "blocked", "red", None, "Prompt injection detected")
        events.append({"agent": "SecurityAgent", "message": "ALERT: Prompt injection attempt detected and blocked.", "tier": "red"})
        update_incident(incident_id, status="escalated", resolution_summary="Prompt injection detected. Incident escalated.")
        metrics = _log_metrics(incident_id, "escalated", start, tool_calls)
        return {"status": "escalated", "events": events, "runbook_id": None, "metrics": metrics}

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
    tool_calls += len(diagnostics)
    for d in diagnostics:
        _log(incident_id, "DiagnosticAgent", "diagnosis", d["safety_tier"], d["command"], d["stdout"])
        events.append({"agent": "DiagnosticAgent", "message": f"Ran: {d['command']}", "tier": d["safety_tier"]})

    # Step 3b: Cross-agent disagreement resolution
    diag_assessment = diagnostic_assess(diagnostics, classification["category"])
    sec_assessment = assess_prompt(user_prompt)

    # When the security agent finds nothing, its assessment should mirror the
    # diagnostic reading so benign incidents don't produce false disagreements.
    if not sec_assessment.get("security_flagged"):
        sec_assessment["root_cause"] = diag_assessment["root_cause"]

    reconciliation = reconcile_assessments(diag_assessment, sec_assessment)

    if reconciliation.get("disagreement"):
        _log(incident_id, "IncidentCommander", "disagreement", "yellow", None, reconciliation["detail"])
        events.append({
            "agent": "IncidentCommander",
            "message": f"Disagreement detected: {reconciliation['competing_hypotheses'][0]['hypothesis']} vs {reconciliation['competing_hypotheses'][1]['hypothesis']}.",
            "tier": "yellow",
        })
        events.append({
            "agent": "IncidentCommander",
            "message": f"Reconciled in favor of {reconciliation['reconciled_by']}: {reconciliation['decision']}",
            "tier": "green",
        })
    elif reconciliation.get("decision"):
        events.append({
            "agent": "IncidentCommander",
            "message": f"Agents agree on root cause: {reconciliation['decision']}",
            "tier": "green",
        })

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
                update_incident(incident_id, status="awaiting_approval", runbook_id=runbook.get("runbook_id"))
                metrics = _log_metrics(incident_id, "awaiting_approval", start, tool_calls)
                return {"status": "awaiting_approval", "events": events, "runbook_id": runbook.get("runbook_id"), "pending_command": cmd, "metrics": metrics}

            output = executor.run(cmd)
            tool_calls += 1
            _log(incident_id, "DiagnosticAgent", "remediation", "yellow", cmd, output["stdout"])
            events.append({"agent": "DiagnosticAgent", "message": f"Executed: {cmd}", "tier": "yellow"})

        return _finalize_runbook(incident_id, runbook, events, start, tool_calls)

    # No runbook found - escalate
    incident = get_incident(incident_id)
    ticket = generate_escalation_ticket(incident, get_audit(incident_id))
    update_incident(incident_id, status="escalated", resolution_summary="No matching runbook found. Escalated to Tier 2.")
    _log(incident_id, "IncidentCommander", "escalation", "yellow", None, json.dumps(ticket))
    events.append({"agent": "IncidentCommander", "message": "No runbook matched. Escalating to Tier 2 human support.", "tier": "yellow"})
    metrics = _log_metrics(incident_id, "escalated", start, tool_calls)
    return {"status": "escalated", "events": events, "runbook_id": None, "escalation_ticket": ticket, "metrics": metrics}


def approve_action(incident_id: str, command: str) -> dict:
    start = time.perf_counter()
    tool_calls = 0

    # Re-validate the approved command through the safety gate. A RED command
    # must NEVER execute, even if submitted through the approval endpoint.
    approval = check_action(command)

    if not approval["allowed"]:
        _log(incident_id, "SecurityAgent", "blocked", "red", command, approval["reason"])
        metrics = _log_metrics(incident_id, "blocked", start, tool_calls)
        return {
            "status": "blocked",
            "events": [
                {"agent": "SecurityAgent", "message": f"BLOCKED: {command} — {approval['reason']}", "tier": "red"},
            ],
            "metrics": metrics,
        }

    _log(incident_id, "DiagnosticAgent", "approval", "yellow", command, "User approved execution")
    output = executor.run(command)
    tool_calls += 1
    _log(incident_id, "DiagnosticAgent", "remediation", "yellow", command, output["stdout"])

    events = [
        {"agent": "DiagnosticAgent", "message": f"Executed approved command: {command}", "tier": "yellow"},
    ]

    incident = get_incident(incident_id)
    runbook_id = incident.get("runbook_id")
    runbook = _find_runbook(runbook_id) if runbook_id else None
    if runbook:
        # Human approved this certified runbook: resume and complete the
        # remaining remediation steps, then verify resolution.
        steps = runbook.get("remediation_steps", [])
        approved_idx = _step_index(steps, command)
        remaining = steps[approved_idx + 1:] if approved_idx is not None else []
        for step in remaining:
            cmd = step.get("command", "")
            step_approval = check_action(cmd)
            if not step_approval["allowed"]:
                _log(incident_id, "SecurityAgent", "blocked", "red", cmd, step_approval["reason"])
                events.append({"agent": "SecurityAgent", "message": f"BLOCKED: {cmd} — {step_approval['reason']}", "tier": "red"})
                continue
            step_output = executor.run(cmd)
            tool_calls += 1
            _log(incident_id, "DiagnosticAgent", "remediation", "yellow", cmd, step_output["stdout"])
            events.append({"agent": "DiagnosticAgent", "message": f"Executed: {cmd}", "tier": "yellow"})

        return _finalize_runbook(incident_id, runbook, events, start, tool_calls)

    update_incident(incident_id, status="resolved", resolution_summary=f"Approved and executed: {command}")
    events.append({"agent": "IncidentCommander", "message": "Incident resolved after approved remediation.", "tier": "green"})
    return _with_report(incident_id, "resolved", events, start, tool_calls)


def _finalize_runbook(incident_id: str, runbook: dict, events: list, start: float, tool_calls: int) -> dict:
    """Run the runbook's verification spec and resolve or escalate accordingly."""
    verification = _run_verification(incident_id, runbook, executor, events)
    tool_calls += verification["tool_calls"]

    runbook_id = runbook.get("runbook_id")
    if verification["passed"]:
        update_incident(incident_id, status="resolved",
                        resolution_summary=f"Resolved via runbook {runbook_id}",
                        runbook_id=runbook_id)
        events.append({"agent": "IncidentCommander", "message": "Verification passed. Incident resolved successfully.", "tier": "green"})
        return _with_report(incident_id, "resolved", events, start, tool_calls)

    incident = get_incident(incident_id)
    ticket = generate_escalation_ticket(incident, get_audit(incident_id))
    update_incident(incident_id, status="escalated",
                    resolution_summary=f"Remediation applied but verification failed for runbook {runbook_id}. Escalated to Tier 2.",
                    runbook_id=runbook_id)
    _log(incident_id, "IncidentCommander", "escalation", "yellow", None, json.dumps(ticket))
    events.append({"agent": "IncidentCommander", "message": "Verification failed. Escalating to Tier 2 with full telemetry.", "tier": "red"})
    metrics = _log_metrics(incident_id, "escalated", start, tool_calls)
    return {"status": "escalated", "events": events, "runbook_id": runbook_id, "escalation_ticket": ticket, "metrics": metrics}


def _run_verification(incident_id: str, runbook: dict, exe, events: list) -> dict:
    verifications = runbook.get("verification", [])
    if not verifications:
        return {"passed": True, "tool_calls": 0, "passed_checks": 0, "total": 0}

    tool_calls = 0
    passed_checks = 0
    for v in verifications:
        cmd = v.get("command", "")
        expected = v.get("expected_output_regex", "")
        output = exe.run(cmd)
        tool_calls += 1
        matched = bool(re.search(expected, output.get("stdout", ""), re.IGNORECASE)) if expected else True
        _log(incident_id, "DiagnosticAgent", "verification", "green", cmd, output.get("stdout"))
        events.append({"agent": "DiagnosticAgent", "message": f"Verification {'PASSED' if matched else 'FAILED'}: {cmd} (expected ~{expected})", "tier": "green" if matched else "yellow"})
        if matched:
            passed_checks += 1

    return {"passed": passed_checks == tool_calls and tool_calls > 0, "tool_calls": tool_calls, "passed_checks": passed_checks, "total": tool_calls}


def _find_runbook(runbook_id: str):
    for rb in load_all_runbooks():
        if rb.get("runbook_id") == runbook_id:
            return rb
    return None


def _step_index(steps: list, command: str):
    for i, step in enumerate(steps):
        if step.get("command") == command:
            return i
    return None


def _with_report(incident_id: str, status: str, events: list, start: float, tool_calls: int) -> dict:
    incident = get_incident(incident_id)
    report = generate_report(incident, get_audit(incident_id))
    saved_report = _save_report(incident_id, report)
    events.append({"agent": "IncidentCommander", "message": "Incident report generated.", "tier": "green"})
    metrics = _log_metrics(incident_id, status, start, tool_calls)
    return {"status": status, "events": events, "runbook_id": incident.get("runbook_id"), "report_path": saved_report, "metrics": metrics}


def _save_report(incident_id: str, report: str) -> str:
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{incident_id}.md")
    with open(path, "w") as f:
        f.write(report)
    return path


def _log_metrics(incident_id: str, status: str, start: float, tool_calls: int) -> dict:
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    metrics = {
        "status": status,
        "latency_ms": latency_ms,
        "tool_calls": tool_calls,
    }
    insert_audit({
        "incident_id": incident_id,
        "timestamp": datetime.utcnow().isoformat(),
        "agent_name": "IncidentCommander",
        "action_type": "metrics",
        "safety_tier": "green",
        "command_executed": None,
        "output": json.dumps(metrics),
    })
    return metrics


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