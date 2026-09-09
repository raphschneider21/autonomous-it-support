"""Reports incidents to the monitoring service.

`MONITORING_URL` decides where the service desk lives. It defaults to localhost,
so a single-machine setup works with no configuration; for the demo the Ubuntu
VM points at the Mac:

    MONITORING_URL=http://10.211.55.2:8001

**Reporting never blocks the fix.** Every failure — service down, wrong host,
DNS, timeout — is swallowed and recorded locally. A service desk that cannot be
reached is an IT visibility problem; it is not a reason to leave a user's
machine broken. This is the mitigation for the VM-to-host networking risk: if
the network sulks five minutes before recording, the agent still works and only
the dashboard goes quiet.
"""
import json
import os
import urllib.error
import urllib.request

DEFAULT_URL = "http://127.0.0.1:8001"
TIMEOUT_SECONDS = 2.0

_last_error: str | None = None


def monitoring_url() -> str:
    return os.environ.get("MONITORING_URL", DEFAULT_URL).rstrip("/")


def enabled() -> bool:
    """False disables reporting entirely (offline rehearsal, unit tests)."""
    return os.environ.get("MONITORING_ENABLED", "1") not in ("0", "false", "no")


def last_error() -> str | None:
    """Why the most recent report failed, for the agent's own audit trail."""
    return _last_error


def report(payload: dict) -> bool:
    """Send a ticket report. Returns True on success, never raises."""
    global _last_error

    if not enabled():
        _last_error = "disabled"
        return False

    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        f"{monitoring_url()}/api/tickets",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            _last_error = None
            return 200 <= response.status < 300
    except urllib.error.HTTPError as exc:
        _last_error = f"HTTP {exc.code} from monitoring service"
    except urllib.error.URLError as exc:
        _last_error = f"monitoring service unreachable at {monitoring_url()}: {exc.reason}"
    except Exception as exc:  # noqa: BLE001 - reporting must never raise
        _last_error = f"monitoring report failed: {exc}"
    return False


def build_report(incident: dict, audit: list[dict], result: dict,
                 hostname: str = None) -> dict:
    """Shape an incident, its audit trail and its result into a ticket report.

    `actions` is what the service desk actually reads: the ordered list of what
    each agent did, with the safety tier attached, so a technician can see the
    reasoning without opening the endpoint. `errors` separates out the refusals
    and failures, because those are what someone is paging through the dashboard
    to find.
    """
    actions, errors = [], []
    for entry in audit or []:
        item = {
            "timestamp": entry.get("timestamp"),
            "agent": entry.get("agent_name"),
            "action": entry.get("action_type"),
            "tier": entry.get("safety_tier"),
            "command": entry.get("command_executed"),
            "output": (entry.get("output") or "")[:800],
        }
        actions.append(item)
        if entry.get("safety_tier") == "red" or entry.get("action_type") == "blocked":
            errors.append(item)

    metrics = result.get("metrics") or {}
    usage = result.get("usage") or {}

    return {
        "incident_id": incident.get("id") or incident.get("incident_id"),
        "hostname": hostname or os.environ.get("ENDPOINT_HOSTNAME") or _hostname(),
        "title": (incident.get("user_prompt") or "")[:120],
        "status": result.get("status", "open"),
        "category": incident.get("category"),
        "severity": incident.get("severity"),
        "user_prompt": incident.get("user_prompt"),
        "runbook_id": result.get("runbook_id") or incident.get("runbook_id"),
        "resolution": incident.get("resolution_summary"),
        "agent_source": result.get("agent_source"),
        "latency_ms": metrics.get("latency_ms"),
        "tool_calls": metrics.get("tool_calls"),
        "tokens_in": usage.get("input_tokens", 0),
        "tokens_out": usage.get("output_tokens", 0),
        "actions": actions,
        "errors": errors,
        "escalation": result.get("escalation_ticket"),
        "user_confirmed": incident.get("user_confirmed"),
    }


def _hostname() -> str:
    import socket

    try:
        return socket.gethostname()
    except Exception:  # noqa: BLE001
        return "unknown-endpoint"
