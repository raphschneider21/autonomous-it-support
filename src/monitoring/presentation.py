"""Derives the product vocabulary the Service Desk shows from stored ticket state.

Two reasons this lives in the backend rather than the browser.

First, the queue, the ticket detail and Live Operations must never disagree
about who owns a ticket. Deriving ownership once, server-side, makes that
structural rather than a convention three views have to remember.

Second, it is testable. "A `still_broken` verdict moves the ticket to HUMAN L2"
is the single most important claim the demo makes about this system, and it
should be asserted in a test rather than inspected by eye on a projector.

Nothing here invents state. Every value is a rename or a direct consequence of
data the endpoint already reported.
"""

AUTOMATED_L1 = "AUTOMATED L1"
HUMAN_L2 = "HUMAN L2"


def support_level(status: str, user_confirmed: str = None) -> str:
    """Who owns the ticket right now.

    The rule is deliberately simple, because the audience has to follow it from
    a projector: escalation is the only thing that moves a ticket to a human.
    """
    return HUMAN_L2 if status == "escalated" else AUTOMATED_L1


def display_status(status: str, user_confirmed: str = None) -> str:
    """Operational wording for a database state.

    `open` is the interesting case: it means two very different things
    depending on whether the automation has finished. A ticket the endpoint has
    verified but the employee has not yet confirmed is *awaiting the user*, not
    "open" in the sense of untouched.
    """
    if status == "escalated":
        return "ESCALATED"
    if status == "closed":
        return "CLOSED"
    if status == "diagnosing":
        return "INVESTIGATING"
    if status == "open" and user_confirmed is None:
        return "INVESTIGATING"
    return "AWAITING USER"


def is_false_resolution(ticket: dict) -> bool:
    """Technical verification passed, but the employee says it is still broken.

    The single most valuable signal this system produces, because no automated
    check can see it. Treated as a first-class ticket property rather than a
    status string, so the UI can give it the weight it deserves.
    """
    if ticket.get("user_confirmed") != "still_broken":
        return False
    return any(
        action.get("action") == "verification"
        for action in (ticket.get("actions") or [])
    )


def was_refused(ticket: dict) -> bool:
    """A policy or safety boundary stopped this incident."""
    return any(
        action.get("action") == "blocked" or action.get("tier") == "red"
        for action in (ticket.get("actions") or [])
    )


def executed_commands(ticket: dict) -> list:
    """Commands that actually ran, as opposed to ones that were refused."""
    return [
        action for action in (ticket.get("actions") or [])
        if action.get("command") and action.get("action") in
        ("diagnosis", "remediation", "verification")
    ]


def escalation_reason(ticket: dict) -> str:
    """Why a human is now looking at this, in one sentence.

    Ordered by what a technician most needs to know first: a refusal is a
    different kind of handoff from a fix that did not hold.
    """
    if ticket.get("status") != "escalated":
        return ""
    if was_refused(ticket):
        return ("The request was refused by the safety policy. No remediation "
                "was executed on the endpoint.")
    if is_false_resolution(ticket):
        return ("Technical verification passed, but the employee reports the "
                "problem is still present. Automated Tier 1 is exhausted.")
    if ticket.get("user_confirmed") == "still_broken":
        return "The employee reports the problem is still present."
    if not ticket.get("runbook_id"):
        return ("No operational runbook matched this incident and no confident "
                "remediation could be derived.")
    return ticket.get("resolution") or "Automated Tier 1 could not resolve this incident."


def presentation(ticket: dict) -> dict:
    """Derived fields added to every ticket the API returns."""
    status = ticket.get("status") or "open"
    confirmed = ticket.get("user_confirmed")
    return {
        "support_level": support_level(status, confirmed),
        "display_status": display_status(status, confirmed),
        "false_resolution": is_false_resolution(ticket),
        "refused": was_refused(ticket),
        "escalation_reason": escalation_reason({**ticket, "status": status}),
        "escalated_from_automation": status == "escalated",
    }


# --------------------------------------------------------------------------
# Trace vocabulary
# --------------------------------------------------------------------------
# Maps the audit `action_type` the endpoint records onto the component labels
# the demo plan uses. This is a rename, not an invention: every label below is
# backed by a real audit row.
#
# Note the absence of KNOWLEDGE. The demo plan's Live Operations example shows a
# timestamped "runbook matched" line, but the engine records the match only as a
# streamed UI event — there is no audit row and therefore no real timestamp. The
# runbook is shown in the trace as an untimed context line rather than given a
# fabricated one. Adding that audit entry is an endpoint-side change (Dev1).

COMPONENT_BY_ACTION = {
    "input_check": "SECURITY",
    "blocked": "REFUSED",
    "classification": "TRIAGE",
    "diagnosis": "DIAGNOSTIC",
    "remediation": "EXECUTOR",
    "verification": "VERIFY",
    "disagreement": "COMMANDER",
    "escalation": "COMMANDER",
    "metrics": "COMMANDER",
    "monitoring_unreachable": "SYSTEM",
}

# Ordinary diagnostic noise the audience does not need on the big screen.
TRACE_HIDDEN_ACTIONS = {"monitoring_unreachable"}


def component_for(action: dict) -> str:
    """Component label for one audit entry."""
    if action.get("tier") == "red":
        return "REFUSED"
    return COMPONENT_BY_ACTION.get(action.get("action"), (action.get("agent") or "SYSTEM").upper())


def trace(ticket: dict) -> list:
    """Chronological component trace for Live Operations.

    Returns the audit entries the endpoint actually reported, relabelled and
    with a short outcome line. Deliberately not padded with lifecycle steps that
    were inferred rather than recorded — a trace that mixes the two cannot be
    trusted as evidence.
    """
    rows = []
    for action in (ticket.get("actions") or []):
        if action.get("action") in TRACE_HIDDEN_ACTIONS:
            continue
        rows.append({
            "timestamp": action.get("timestamp"),
            "component": component_for(action),
            "action": action.get("action"),
            "tier": action.get("tier") or "green",
            "command": action.get("command"),
            "output": action.get("output"),
            "refused": action.get("tier") == "red" or action.get("action") == "blocked",
        })
    return rows


# Lifecycle stages shown in the Timeline tab, in the order they can occur.
# `source` records how each stage was established, so the UI can present an
# inferred stage differently from a recorded one.
LIFECYCLE = [
    ("Incident created", ("input_check",), "recorded"),
    ("Security policy check", ("input_check", "blocked"), "recorded"),
    ("Triage", ("classification",), "recorded"),
    ("Diagnostics", ("diagnosis",), "recorded"),
    ("Remediation", ("remediation",), "recorded"),
    ("Verification", ("verification",), "recorded"),
]


def timeline(ticket: dict) -> list:
    """Lifecycle stages, each either recorded in the audit trail or inferred.

    Stages with no supporting audit row are omitted rather than shown as
    pending, except the two the ticket state itself establishes — user
    confirmation and closure/escalation — which are labelled `inferred` so the
    UI never presents a derived stage as recorded evidence.
    """
    actions = ticket.get("actions") or []
    by_action = {}
    for entry in actions:
        by_action.setdefault(entry.get("action"), entry)

    stages = []
    if actions:
        first = actions[0]
        stages.append({"stage": "Incident created", "timestamp": first.get("timestamp"),
                       "detail": ticket.get("user_prompt") or "", "source": "recorded"})

    for label, action_types, source in LIFECYCLE[1:]:
        entry = next((by_action[a] for a in action_types if a in by_action), None)
        if not entry:
            continue
        matching = [a for a in actions if a.get("action") in action_types]
        detail = entry.get("output") or entry.get("command") or ""
        if len(matching) > 1:
            detail = f"{len(matching)} steps"
        stages.append({"stage": label, "timestamp": entry.get("timestamp"),
                       "detail": str(detail)[:160], "source": source,
                       "tier": entry.get("tier")})

    if ticket.get("runbook_id"):
        stages.append({"stage": "Runbook applied", "timestamp": None,
                       "detail": ticket["runbook_id"], "source": "inferred"})

    confirmed = ticket.get("user_confirmed")
    if confirmed:
        stages.append({
            "stage": "Employee confirmation",
            "timestamp": None,
            "detail": "Confirmed solved" if confirmed == "solved" else "Reported still broken",
            "source": "inferred",
            "tier": "green" if confirmed == "solved" else "yellow",
        })

    status = ticket.get("status")
    if status in ("closed", "escalated"):
        stages.append({
            "stage": "Escalated to Human Tier 2" if status == "escalated" else "Ticket closed",
            "timestamp": ticket.get("updated_at"),
            "detail": escalation_reason(ticket) if status == "escalated" else (ticket.get("resolution") or ""),
            "source": "inferred",
            "tier": "yellow" if status == "escalated" else "green",
        })
    return stages
