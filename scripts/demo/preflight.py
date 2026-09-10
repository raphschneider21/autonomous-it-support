#!/usr/bin/env python3
"""Fail-fast readiness gate for the deterministic final-demo endpoint.

The checks use the Python standard library and the runtime's optional .env
loader. Network calls are limited to the endpoint and configured Service Desk.
The full check deliberately resets simulated state; run it before a scenario.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


TRUE_VALUES = {"1", "true", "yes", "on"}
DETERMINISTIC_MODES = {"deterministic", "fallback", "mock", "offline"}


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def check_environment(env: dict[str, str] | None = None) -> list[Check]:
    """Validate the local process configuration before starting uvicorn."""
    env = os.environ if env is None else env
    executor = env.get("EXECUTOR", "mock").strip().lower()
    demo_mode = env.get("DEMO_MODE", "0").strip().lower()
    agent_mode = env.get("AGENT_MODE", "auto").strip().lower()
    monitoring = env.get("MONITORING_ENABLED", "1").strip().lower()
    target = env.get("MONITORING_URL", "http://127.0.0.1:8001").rstrip("/")
    key_present = bool(env.get("ANTHROPIC_API_KEY", "").strip())

    checks = [
        Check("mock executor", executor == "mock", f"EXECUTOR={executor}"),
        Check("demo mode", demo_mode in TRUE_VALUES, f"DEMO_MODE={demo_mode}"),
        Check(
            "deterministic agents",
            agent_mode in DETERMINISTIC_MODES,
            f"AGENT_MODE={agent_mode}; external key {'present' if key_present else 'absent'}",
        ),
        Check("monitoring enabled", monitoring in TRUE_VALUES,
              f"MONITORING_ENABLED={monitoring}"),
        Check("monitoring target", target.startswith(("http://", "https://")),
              f"MONITORING_URL={target}"),
        Check("Ubuntu runbooks", env.get("RUNBOOK_STORE", "ubuntu-26.04") == "ubuntu-26.04",
              f"RUNBOOK_STORE={env.get('RUNBOOK_STORE', 'ubuntu-26.04')}"),
    ]
    return checks


def check_bind_available(endpoint_url: str) -> Check:
    """Detect an occupied endpoint port before the launcher starts uvicorn."""
    try:
        parsed = urlparse(endpoint_url)
        host = parsed.hostname or "127.0.0.1"
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        bind_host = "127.0.0.1" if host in ("localhost", "0.0.0.0") else host
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.bind((bind_host, port))
        finally:
            sock.close()
        return Check("endpoint port", True, f"{host}:{port} is available")
    except (ValueError, OSError) as exc:
        return Check("endpoint port", False, f"{endpoint_url} is unavailable: {exc}")


def _request_json(url: str, method: str = "GET", timeout: float = 2.0) -> dict | list:
    request = urllib.request.Request(url, method=method)
    with urllib.request.urlopen(request, timeout=timeout) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"HTTP {response.status}")
        return json.loads(response.read().decode("utf-8"))


def check_running_services(endpoint_url: str) -> list[Check]:
    """Verify health, reset the canonical state, and reach the Service Desk."""
    checks: list[Check] = []
    endpoint_url = endpoint_url.rstrip("/")
    try:
        health = _request_json(f"{endpoint_url}/api/health")
        runtime_ok = (
            health.get("endpoint") == "ubuntu-demo-01"
            and health.get("executor") == "mock"
            and health.get("executes_on_this_machine") is False
            and health.get("demo_mode") is True
            and health.get("agent_mode") == "deterministic"
            and health.get("external_model_enabled") is False
            and health.get("requested_executor") == "mock"
            and health.get("requested_agent_mode") in DETERMINISTIC_MODES
            and health.get("runbook_store") == "ubuntu-26.04"
        )
        checks.append(Check("endpoint runtime", runtime_ok, json.dumps(health, sort_keys=True)))
    except Exception as exc:  # noqa: BLE001 - rendered as a failed check
        health = {}
        checks.append(Check("endpoint runtime", False, str(exc)))

    checks.append(Check("endpoint monitoring", health.get("monitoring_enabled") is True
                        and health.get("monitoring_reachable") is True,
                        f"enabled={health.get('monitoring_enabled')}; "
                        f"reachable from endpoint={health.get('monitoring_reachable')}"))

    # Do not mutate a different app or an unsafe/misconfigured runtime.
    if not checks[0].ok:
        checks.append(Check("canonical reset", False, "Skipped: correct demo runtime not verified"))
        return checks

    try:
        state = _request_json(f"{endpoint_url}/api/demo/reset", method="POST")
        observed = _request_json(f"{endpoint_url}/api/demo/state")
        repeated = _request_json(f"{endpoint_url}/api/demo/reset", method="POST")
        reset_ok = (
            state.get("endpoint") == "ubuntu-demo-01"
            and state.get("mode") == "simulated"
            and state.get("services", {}).get("cups") == "active"
            and state.get("active_faults") == []
            and state.get("print_queue") == "empty"
            and "cups_stopped" in {f["id"] for f in state.get("available_faults", [])}
            and state == observed == repeated
        )
        checks.append(Check("canonical reset", reset_ok, json.dumps(state, sort_keys=True)))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("canonical reset", False, str(exc)))

    try:
        runbooks = _request_json(f"{endpoint_url}/api/runbooks")
        cups_present = any(rb.get("id") == "RB-CUPS-001" for rb in runbooks)
        checks.append(Check("CUPS runbook", cups_present, "RB-CUPS-001 must be available"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("CUPS runbook", False, str(exc)))

    target = health.get("monitoring_url") or os.environ.get(
        "MONITORING_URL", "http://127.0.0.1:8001"
    )
    try:
        desk = _request_json(f"{target.rstrip('/')}/api/health")
        checks.append(Check("Service Desk", desk.get("status") == "ok" and desk.get("service") == "monitoring",
                            f"{target}: {json.dumps(desk, sort_keys=True)}"))
    except Exception as exc:  # noqa: BLE001
        checks.append(Check("Service Desk", False, f"{target}: {exc}"))
    return checks


def run_preflight(endpoint_url: str, environment_only: bool = False,
                  check_bind: bool = False,
                  env: dict[str, str] | None = None) -> list[Check]:
    # A running server's health is authoritative; the preflight shell may use
    # different environment variables. Inspect local config only before launch.
    checks = check_environment(env) if environment_only else check_running_services(endpoint_url)
    if check_bind:
        checks.append(check_bind_available(endpoint_url))
    return checks


def main(argv: list[str] | None = None) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from src import config
    config.load()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--endpoint-url", default=os.environ.get(
        "DEMO_ENDPOINT_URL", "http://127.0.0.1:8000"))
    parser.add_argument("--environment-only", action="store_true")
    parser.add_argument("--check-bind", action="store_true")
    args = parser.parse_args(argv)

    checks = run_preflight(args.endpoint_url, args.environment_only, args.check_bind)
    for check in checks:
        print(f"[{'PASS' if check.ok else 'FAIL'}] {check.name}: {check.detail}")
    ready = all(check.ok for check in checks)
    print("READY" if ready else "NOT READY")
    return 0 if ready else 1


if __name__ == "__main__":
    sys.exit(main())
