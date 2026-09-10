"""Reports incidents to the monitoring service.

`MONITORING_URL` decides where the Service Desk lives. It defaults to localhost,
which is also the current graded-demo topology:

    MONITORING_URL=http://127.0.0.1:8001

The endpoint/runtime service and Service Desk still communicate over HTTP and
keep separate state even though both processes run on the same Mac. The managed
endpoint represented by the runtime is the explicitly simulated Ubuntu 26.04
endpoint `ubuntu-demo-01`.

**Reporting never blocks the fix.** Every failure — service down, wrong host,
DNS, timeout — is swallowed and recorded locally. A Service Desk outage is an
IT-visibility problem; it is not a reason to stop endpoint troubleshooting.
"""
import json
import os
import urllib.error
import urllib.request
from .. import config

DEFAULT_URL = "http://127.0.0.1:8001"
TIMEOUT_SECONDS = 2.0
HEALTH_TIMEOUT_SECONDS = 0.5

_last_error: str | None = None


def monitoring_url() -> str:
    return os.environ.get("MONITORING_URL", DEFAULT_URL).rstrip("/")


def enabled() -> bool:
    """False disables reporting entirely (offline rehearsal, unit tests)."""
    return os.environ.get("MONITORING_ENABLED", "1").strip().lower() not in ("0", "false", "no", "off")


def last_error() -> str | None:
    """Why the most recent report failed, for the agent's own audit trail."""
    return _last_error


def reachable() -> bool | None:
    """Probe Service Desk health without changing ticket state.

    ``None`` means monitoring is deliberately disabled.  This check is used by
    health/preflight only; incident processing never depends on it.
    """
    if not enabled():
        return None
    try:
        request = urllib.request.Request(f"{monitoring_url()}/api/health", method="GET")
        with urllib.request.urlopen(request, timeout=HEALTH_TIMEOUT_SECONDS) as response:
            health = json.loads(response.read().decode("utf-8"))
            return (200 <= response.status < 300 and health.get("status") == "ok"
                    and health.get("service") == "monitoring")
    except Exception:  # noqa: BLE001 - readiness should report, not raise
        return False


def report(payload: dict) -> bool:
    """Send a ticket report. Returns True on success, never raises."""
    global _last_error

    if not enabled():
        _last_error = "disabled"
        return False

    try:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{monitoring_url()}/api/tickets",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            success = 200 <= response.status < 300
            _last_error = None if success else f"HTTP {response.status} from monitoring service"
            return success
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
    # Token totals ride along on metrics — the commander aggregates them across
    # the four agents as each one answers.
    usage = result.get("usage") or metrics

    return {
        "incident_id": incident.get("id") or incident.get("incident_id"),
        "hostname": hostname or incident.get("hostname") or config.endpoint_name(),
        "title": (incident.get("user_prompt") or "")[:120],
        "status": result.get("status", "open"),
        "category": incident.get("category"),
        "severity": incident.get("severity"),
        "user_prompt": incident.get("user_prompt"),
        "runbook_id": result.get("runbook_id") or incident.get("runbook_id"),
        "resolution": incident.get("resolution_summary"),
        "agent_source": result.get("agent_source") or (
            "deterministic" if not config.external_model_enabled() else
            ("claude" if metrics.get("agents_called") else "fallback") if metrics else None
        ),
        "latency_ms": metrics.get("latency_ms"),
        "tool_calls": metrics.get("tool_calls"),
        "tokens_in": usage.get("input_tokens", 0),
        "tokens_out": usage.get("output_tokens", 0),
        "actions": actions,
        "errors": errors,
        "escalation": result.get("escalation_ticket"),
        "user_confirmed": incident.get("user_confirmed"),
        # Additive fields consumed by the final Service Desk workstream.  The
        # incident report is displayable content, never an Ubuntu-only path.
        "incident_report": result.get("incident_report"),
        "runbook": result.get("runbook"),
        "lifecycle_stage": result.get("lifecycle_stage"),
        "support_level": (
            "human_l2" if result.get("status") == "escalated" else "automated_l1"
        ),
    }


def _hostname() -> str:
    import socket

    try:
        return socket.gethostname()
    except Exception:  # noqa: BLE001
        return "unknown-endpoint"
