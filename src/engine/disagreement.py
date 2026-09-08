SECURITY_ROOT_CAUSE_PREFIX = "security/"


def reconcile_assessments(
    diagnostic_assessment: dict,
    security_assessment: dict,
) -> dict:
    """Reconcile conflicting agent hypotheses.

    Each assessment is a dict of the form:
        {"agent": str, "root_cause": str, "evidence": str}

    Returns a dict describing agreement/disagreement and the final decision.
    When the agents disagree, the security reading wins by default because it
    is the conservative, safety-first interpretation.
    """
    if not diagnostic_assessment or not security_assessment:
        missing = []
        if not diagnostic_assessment:
            missing.append("DiagnosticAgent")
        if not security_assessment:
            missing.append("SecurityAgent")
        return {
            "disagreement": False,
            "decision": None,
            "detail": "Insufficient agent output to compare hypotheses.",
            "missing_agents": missing,
        }

    diag_cause = diagnostic_assessment.get("root_cause")
    sec_cause = security_assessment.get("root_cause")

    if diag_cause == sec_cause:
        return {
            "disagreement": False,
            "decision": diag_cause,
            "detail": "All agents agree on the root cause.",
            "competing_hypotheses": [],
        }

    hypotheses = [
        {
            "agent": "DiagnosticAgent",
            "hypothesis": diag_cause,
            "evidence": diagnostic_assessment.get("evidence"),
        },
        {
            "agent": "SecurityAgent",
            "hypothesis": sec_cause,
            "evidence": security_assessment.get("evidence"),
        },
    ]

    if sec_cause and sec_cause.startswith(SECURITY_ROOT_CAUSE_PREFIX):
        decision = sec_cause
        reconciled_by = "SecurityAgent"
    else:
        decision = diag_cause
        reconciled_by = "DiagnosticAgent"

    return {
        "disagreement": True,
        "decision": decision,
        "reconciled_by": reconciled_by,
        "detail": (
            f"Agents disagreed ({diag_cause} vs {sec_cause}). "
            f"Incident Commander reconciled in favor of {reconciled_by} based on evidence weight."
        ),
        "competing_hypotheses": hypotheses,
    }