import json
import os
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from ..models import IncidentStatus, SafetyTier
from ..database import insert_incident, update_incident, get_incident, insert_audit
from .triage_agent import classify
from .diagnostic_agent import diagnose, assess as diagnostic_assess, verify_fix
from .security_agent import check_action, detect_prompt_injection, assess_prompt
from . import llm
from .disagreement import reconcile_assessments
from .event_stream import store
from ..knowledge.runbook_matcher import match_runbook
from ..knowledge.runbook_parser import load_all_runbooks
from ..integrations.escalation import generate_escalation_ticket
from ..integrations import monitoring_client
from ..documentation.report_generator import generate_report
from ..executors.factory import get_executor

# Per-incident token totals, read back when the result is assembled.
_usage_by_incident: dict[str, dict] = {}


def _emit(incident_id: str, event: dict):
    """Push a single event to the incident's live SSE stream."""
    store.push(incident_id, event)


def _push(incident_id: str, events: list, event: dict):
    """Append to the events list AND push to the live SSE stream."""
    events.append(event)
    _emit(incident_id, event)


def _collect_usage(*agent_results) -> dict:
    """Sum token usage across the agents that ran this incident.

    Each agent result carries `_usage` when Claude answered and omits it when
    the deterministic fallback ran, so the totals are a measurement of what the
    model actually cost — not an estimate — and `agents_called` records how many
    of the four used the model at all.
    """
    total = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
             "agents_called": 0, "models": []}
    for result in agent_results:
        usage = (result or {}).get("_usage")
        if not usage:
            continue
        total["input_tokens"] += usage.get("input_tokens", 0)
        total["output_tokens"] += usage.get("output_tokens", 0)
        total["cache_read_input_tokens"] += usage.get("cache_read_input_tokens", 0)
        total["agents_called"] += 1
        total["models"].append(usage.get("model"))
    return total


def run_incident(incident_id: str, user_prompt: str) -> dict:
    start = time.perf_counter()
    tool_calls = 0
    insert_incident(incident_id, user_prompt)
    events = []

    # Step 1: Security check
    if detect_prompt_injection(user_prompt):
        _log(incident_id, "SecurityAgent", "blocked", "red", None, "Prompt injection detected")
        _push(incident_id, events, {"agent": "SecurityAgent", "message": "ALERT: Prompt injection attempt detected and blocked.", "tier": "red"})
        incident = get_incident(incident_id)
        ticket = generate_escalation_ticket(incident, get_audit(incident_id))
        update_incident(incident_id, status="escalated", resolution_summary="Prompt injection detected. Incident escalated.")
        _log(incident_id, "IncidentCommander", "escalation", "yellow", None, json.dumps(ticket.model_dump()))
        metrics = _log_metrics(incident_id, "escalated", start, tool_calls)
        result = {"status": "escalated", "events": events, "runbook_id": None, "escalation_ticket": ticket.model_dump(), "metrics": metrics}
        store.set_result(incident_id, result)
        _report_to_monitoring(incident_id, result)
        return result

    _log(incident_id, "SecurityAgent", "input_check", "green", None, "No injection detected")
    _push(incident_id, events, {"agent": "SecurityAgent", "message": "Input security check passed.", "tier": "green"})

    # Step 2: Triage
    update_incident(incident_id, status="diagnosing")
    classification = classify(user_prompt)
    update_incident(incident_id, category=classification["category"], severity=classification["severity"])
    _log(incident_id, "TriageAgent", "classification", "green", None, json.dumps(classification))
    _push(incident_id, events, {"agent": "TriageAgent", "message": f"Classified as {classification['category']} ({classification['severity']} severity).", "tier": "green"})

    # Step 3: Diagnostic
    executor = get_executor()
    diagnostics = diagnose(classification["category"], executor)
    tool_calls += len(diagnostics)
    for d in diagnostics:
        _log(incident_id, "DiagnosticAgent", "diagnosis", d["safety_tier"], d["command"], d["stdout"])
        _push(incident_id, events, {"agent": "DiagnosticAgent", "message": f"Ran: {d['command']}", "tier": d["safety_tier"]})

    # Step 3b: Diagnostic and Security assess concurrently.
    #
    # These are the two independent readings of the same incident, and running
    # them in parallel is what keeps four model calls inside the 30-second
    # budget: the cheap Security call overlaps the expensive Diagnostic one
    # instead of queueing behind it. Security also sees the diagnostic output,
    # so it can catch instruction-shaped text planted in a log file.
    with ThreadPoolExecutor(max_workers=2) as pool:
        diag_future = pool.submit(diagnostic_assess, diagnostics, classification["category"])
        sec_future = pool.submit(assess_prompt, user_prompt, diagnostics)
        diag_assessment = diag_future.result()
        sec_assessment = sec_future.result()

    if sec_assessment.get("injection_attempt") or diag_assessment.get("injection_observed"):
        _log(incident_id, "SecurityAgent", "blocked", "red", None,
             "Instruction-shaped text found in command output (indirect injection).")
        _push(incident_id, events, {
            "agent": "SecurityAgent",
            "message": "ALERT: instruction-shaped text found in command output. Treated as data and reported, not followed.",
            "tier": "red",
        })

    if not sec_assessment.get("security_flagged"):
        sec_assessment["root_cause"] = diag_assessment["root_cause"]

    reconciliation = _reconcile(diag_assessment, sec_assessment)
    usage = _collect_usage(classification, diag_assessment, sec_assessment, reconciliation)
    _usage_by_incident[incident_id] = usage

    if reconciliation.get("disagreement"):
        _log(incident_id, "IncidentCommander", "disagreement", "yellow", None, reconciliation["detail"])
        _push(incident_id, events, {
            "agent": "IncidentCommander",
            "message": f"Disagreement detected: {reconciliation['competing_hypotheses'][0]['hypothesis']} vs {reconciliation['competing_hypotheses'][1]['hypothesis']}.",
            "tier": "yellow",
        })
        _push(incident_id, events, {
            "agent": "IncidentCommander",
            "message": f"Reconciled in favor of {reconciliation['reconciled_by']}: {reconciliation['decision']}",
            "tier": "green",
        })
    elif reconciliation.get("decision"):
        _push(incident_id, events, {
            "agent": "IncidentCommander",
            "message": f"Agents agree on root cause: {reconciliation['decision']}",
            "tier": "green",
        })

    # Step 4: Runbook match
    runbook = match_runbook(user_prompt)
    if runbook:
        _push(incident_id, events, {"agent": "IncidentCommander", "message": f"Runbook found: {runbook['title']}", "tier": "green"})

        steps = runbook.get("remediation_steps", [])
        for step in steps:
            cmd = step.get("command", "")
            approval = check_action(cmd)

            if not approval["allowed"]:
                _log(incident_id, "SecurityAgent", "blocked", "red", cmd, approval["reason"])
                _push(incident_id, events, {"agent": "SecurityAgent", "message": f"BLOCKED: {cmd} — {approval['reason']}", "tier": "red"})
                continue

            # No second consent. The user consented once, before the run
            # started; a Yellow action executes inside that window. The
            # boundary is enforced by the allowlist, not by a modal the user
            # would click through anyway — anything it does not recognise is
            # RED above and escalates instead of running.
            output = get_executor().run(cmd)
            tool_calls += 1
            _log(incident_id, "DiagnosticAgent", "remediation", approval["safety_tier"], cmd, output["stdout"])
            _push(incident_id, events, {"agent": "DiagnosticAgent", "message": f"Executed: {cmd}", "tier": approval["safety_tier"]})

        return _finalize_runbook(incident_id, runbook, events, start, tool_calls)

    # Step 5: No runbook. This is where the model earns its place — everything
    # above could have been a lookup table. The Diagnostic Agent reasoned from
    # raw probe output to a root cause nobody scripted; if it also proposed a
    # fix it is confident in, try it, under exactly the same allowlist that
    # governs a runbook step.
    _push(incident_id, events, {
        "agent": "IncidentCommander",
        "message": "No runbook matched. Asking the Diagnostic Agent for a reasoned fix.",
        "tier": "green",
    })

    novel = _attempt_novel_remediation(
        incident_id, diag_assessment, classification["category"], events)
    tool_calls += novel["tool_calls"]

    if novel["resolved"]:
        update_incident(incident_id, status="resolved",
                        resolution_summary=f"Resolved without a runbook: {novel['summary']}")
        _push(incident_id, events, {
            "agent": "IncidentCommander",
            "message": "Verified fixed. Resolved from first-principles diagnosis, no runbook required.",
            "tier": "green",
        })
        return _with_report(incident_id, "resolved", events, start, tool_calls)

    # Nothing safe and confident to try, or the attempt did not hold.
    incident = get_incident(incident_id)
    ticket = generate_escalation_ticket(incident, get_audit(incident_id))
    update_incident(incident_id, status="escalated",
                    resolution_summary=novel["summary"])
    _log(incident_id, "IncidentCommander", "escalation", "yellow", None, json.dumps(ticket.model_dump()))
    _push(incident_id, events, {"agent": "IncidentCommander", "message": f"Escalating to Tier 2: {novel['summary']}", "tier": "yellow"})
    metrics = _log_metrics(incident_id, "escalated", start, tool_calls)
    result = {"status": "escalated", "events": events, "runbook_id": None,
              "escalation_ticket": ticket.model_dump(), "metrics": metrics,
              "attempted_command": novel.get("command")}
    store.set_result(incident_id, result)
    _report_to_monitoring(incident_id, result)
    return result


# A proposal the Diagnostic Agent is not confident about is worth less than an
# escalation. Mirrors the retrieval abstention gate in `runbook_matcher`: acting
# on a weak hypothesis is the expensive mistake, not declining to act.
MIN_PROPOSAL_CONFIDENCE = 0.6


def _attempt_novel_remediation(incident_id: str, diag_assessment: dict,
                               category: str, events: list) -> dict:
    """Try the Diagnostic Agent's own proposed fix for an unscripted problem.

    The proposal is model-generated text, so it is treated as exactly that: it
    passes through the same allowlist as any other command, and a refusal is a
    normal outcome rather than an error. Verification re-runs the read-only
    probes and asks the agent whether its own root cause still holds — there is
    no runbook `verification` block to lean on here.
    """
    command = (diag_assessment or {}).get("proposed_command")
    confidence = (diag_assessment or {}).get("confidence") or 0.0

    if not command:
        return {"resolved": False, "tool_calls": 0, "command": None,
                "summary": "No runbook matched and the Diagnostic Agent proposed no fix. "
                           "Escalated to Tier 2 with the full diagnostic record."}

    if confidence < MIN_PROPOSAL_CONFIDENCE:
        _push(incident_id, events, {
            "agent": "DiagnosticAgent",
            "message": f"Proposed '{command}' but only {confidence:.0%} confident. "
                       f"Below the {MIN_PROPOSAL_CONFIDENCE:.0%} floor — not acting on it.",
            "tier": "yellow",
        })
        return {"resolved": False, "tool_calls": 0, "command": command,
                "summary": f"Diagnostic Agent proposed '{command}' at {confidence:.0%} confidence, "
                           f"below the action threshold. Escalated for human judgement."}

    _push(incident_id, events, {
        "agent": "DiagnosticAgent",
        "message": f"Proposed fix ({confidence:.0%} confident): {command}",
        "tier": "yellow",
    })

    approval = check_action(command)
    if not approval["allowed"]:
        # The demo moment worth protecting: the model proposed something and the
        # allowlist refused it, with no human in the loop.
        _log(incident_id, "SecurityAgent", "blocked", "red", command, approval["reason"])
        _push(incident_id, events, {
            "agent": "SecurityAgent",
            "message": f"REFUSED: {command} — {approval['reason']}",
            "tier": "red",
        })
        return {"resolved": False, "tool_calls": 0, "command": command,
                "summary": f"Diagnostic Agent proposed '{command}'; the allowlist refused it. "
                           f"Nothing was executed. Escalated to Tier 2."}

    output = get_executor().run(command)
    _log(incident_id, "DiagnosticAgent", "remediation", approval["safety_tier"], command, output["stdout"])
    _push(incident_id, events, {"agent": "DiagnosticAgent", "message": f"Executed: {command}", "tier": approval["safety_tier"]})

    # Verify by re-probing and asking explicitly whether the fault is gone.
    # There is no runbook `verification` block to lean on here, and inferring
    # success by comparing root-cause prose before and after does not work:
    # those strings almost never match, so everything looked resolved.
    reprobe = diagnose(category, get_executor())
    verdict = verify_fix(diag_assessment.get("root_cause"), command, reprobe)
    _log(incident_id, "DiagnosticAgent", "verification", "green", command,
         json.dumps(verdict))
    tool_calls = 1 + len(reprobe)

    if not verdict["resolved"]:
        _push(incident_id, events, {
            "agent": "DiagnosticAgent",
            "message": f"Re-checked: the fault is still present. {verdict.get('evidence', '')[:150]}",
            "tier": "yellow",
        })
        return {"resolved": False, "tool_calls": tool_calls, "command": command,
                "summary": f"Applied '{command}' but verification shows the problem persists: "
                           f"{verdict.get('evidence', '')[:200]} Escalated with both readings."}

    _push(incident_id, events, {
        "agent": "DiagnosticAgent",
        "message": "Re-checked after the fix: the original root cause is no longer present.",
        "tier": "green",
    })
    return {"resolved": True, "tool_calls": tool_calls, "command": command,
            "summary": f"{diag_assessment.get('root_cause')} — fixed with '{command}'"}


def approve_action(incident_id: str, command: str) -> dict:
    """Removed. Kept as an explicit error so a stale client fails loudly.

    The confirmed safety model is a single up-front consent: the user agrees
    once, before the run, and Green and Yellow actions execute inside that
    window. Anything the allowlist does not recognise is denied and escalated
    rather than offered for approval, so there is nothing left for a per-action
    modal to decide.
    """
    raise NotImplementedError(
        "Per-action approval was removed with the single-consent safety model. "
        "Incidents run to completion (resolved or escalated) in one call."
    )


def _report_to_monitoring(incident_id: str, result: dict) -> None:
    """Push the finished incident to the IT service desk.

    Never raises and never blocks: a monitoring outage costs IT visibility, not
    the user's fix. A failed report is written to the local audit trail so the
    gap is discoverable afterwards rather than silent.
    """
    incident = get_incident(incident_id)
    if not incident:
        return
    payload = monitoring_client.build_report(incident, get_audit(incident_id), result)
    if not monitoring_client.report(payload):
        reason = monitoring_client.last_error()
        if reason != "disabled":
            _log(incident_id, "IncidentCommander", "monitoring_unreachable", "yellow",
                 None, reason or "unknown")


def _reconcile(diag_assessment: dict, sec_assessment: dict) -> dict:
    """Reconcile the two readings. Commander model first, rule-based fallback.

    The deterministic rule ("a security root cause wins") is a reasonable
    default but it is not reasoning — it reaches the same verdict regardless of
    how strong either side's evidence is. The Commander model weighs the actual
    evidence; the rule remains as the declared fallback.
    """
    verdict = llm.call_agent(
        "IncidentCommander",
        "DiagnosticAgent assessment:\n" + json.dumps(diag_assessment, default=str)
        + "\n\nSecurityAgent assessment:\n" + json.dumps(sec_assessment, default=str),
        expect_keys=("decision", "disagreement"),
    )
    if verdict:
        verdict.setdefault("reconciled_by", "IncidentCommander")
        verdict.setdefault("detail", "")
        verdict["competing_hypotheses"] = [
            {"agent": "DiagnosticAgent", "hypothesis": diag_assessment.get("root_cause"),
             "evidence": diag_assessment.get("evidence")},
            {"agent": "SecurityAgent", "hypothesis": sec_assessment.get("root_cause"),
             "evidence": sec_assessment.get("evidence")},
        ]
        return verdict

    return reconcile_assessments(diag_assessment, sec_assessment)


def _finalize_runbook(incident_id: str, runbook: dict, events: list, start: float, tool_calls: int) -> dict:
    """Run the runbook's verification spec and resolve or escalate accordingly."""
    verification = _run_verification(incident_id, runbook, get_executor(), events)
    tool_calls += verification["tool_calls"]

    runbook_id = runbook.get("runbook_id")
    if verification["passed"]:
        update_incident(incident_id, status="resolved",
                        resolution_summary=f"Resolved via runbook {runbook_id}",
                        runbook_id=runbook_id)
        _push(incident_id, events, {"agent": "IncidentCommander", "message": "Verification passed. Incident resolved successfully.", "tier": "green"})
        return _with_report(incident_id, "resolved", events, start, tool_calls)

    incident = get_incident(incident_id)
    ticket = generate_escalation_ticket(incident, get_audit(incident_id))
    update_incident(incident_id, status="escalated",
                    resolution_summary=f"Remediation applied but verification failed for runbook {runbook_id}. Escalated to Tier 2.",
                    runbook_id=runbook_id)
    _log(incident_id, "IncidentCommander", "escalation", "yellow", None, json.dumps(ticket.model_dump()))
    _push(incident_id, events, {"agent": "IncidentCommander", "message": "Verification failed. Escalating to Tier 2 with full telemetry.", "tier": "red"})
    metrics = _log_metrics(incident_id, "escalated", start, tool_calls)
    result = {"status": "escalated", "events": events, "runbook_id": runbook_id, "escalation_ticket": ticket.model_dump(), "metrics": metrics}
    store.set_result(incident_id, result)
    _report_to_monitoring(incident_id, result)
    return result


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
        ev = {"agent": "DiagnosticAgent", "message": f"Verification {'PASSED' if matched else 'FAILED'}: {cmd} (expected ~{expected})", "tier": "green" if matched else "yellow"}
        _push(incident_id, events, ev)
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
    _push(incident_id, events, {"agent": "IncidentCommander", "message": "Incident report generated.", "tier": "green"})
    metrics = _log_metrics(incident_id, status, start, tool_calls)
    result = {"status": status, "events": events, "runbook_id": incident.get("runbook_id"), "report_path": saved_report, "metrics": metrics}
    store.set_result(incident_id, result)
    _report_to_monitoring(incident_id, result)
    return result


def _save_report(incident_id: str, report: str) -> str:
    reports_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "..", "data", "reports")
    os.makedirs(reports_dir, exist_ok=True)
    path = os.path.join(reports_dir, f"{incident_id}.md")
    with open(path, "w") as f:
        f.write(report)
    return path


def _log_metrics(incident_id: str, status: str, start: float, tool_calls: int) -> dict:
    latency_ms = round((time.perf_counter() - start) * 1000, 1)
    usage = _usage_by_incident.pop(incident_id, None) or {}
    metrics = {
        "status": status,
        "latency_ms": latency_ms,
        "tool_calls": tool_calls,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "agents_called": usage.get("agents_called", 0),
        "models": usage.get("models", []),
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