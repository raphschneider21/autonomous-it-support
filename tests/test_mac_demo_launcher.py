"""Regression tests for the Finder-friendly macOS demo launcher."""
from __future__ import annotations

import json
import os

from scripts.demo import mac_runtime


SAFE_ENDPOINT_HEALTH = {
    "status": "ok",
    "endpoint": "ubuntu-demo-01",
    "executor": "mock",
    "requested_executor": "mock",
    "demo_mode": True,
    "agent_mode": "deterministic",
    "requested_agent_mode": "deterministic",
    "external_model_enabled": False,
    "executes_on_this_machine": False,
    "monitoring_enabled": True,
    "monitoring_url": "http://127.0.0.1:8001",
    "monitoring_reachable": True,
    "runbook_store": "ubuntu-26.04",
}


def test_repository_root_resolves_from_helper_location():
    root = mac_runtime.repository_root()
    assert (root / "src" / "main.py").is_file()
    assert (root / "scripts" / "demo" / "launch_all_mac.sh").is_file()


def test_endpoint_health_requires_complete_safe_runtime_profile():
    ok, detail = mac_runtime.validate_health("endpoint", SAFE_ENDPOINT_HEALTH)
    assert ok, detail

    for field, unsafe in (
        ("executor", "real"),
        ("agent_mode", "live"),
        ("demo_mode", False),
        ("monitoring_reachable", False),
        ("monitoring_url", "http://somewhere-else:8001"),
    ):
        payload = {**SAFE_ENDPOINT_HEALTH, field: unsafe}
        accepted, reason = mac_runtime.validate_health("endpoint", payload)
        assert not accepted
        assert field in reason


def test_service_desk_health_has_specific_identity():
    assert mac_runtime.validate_health(
        "service-desk", {"status": "ok", "service": "monitoring"}
    )[0]
    assert not mac_runtime.validate_health(
        "service-desk", {"status": "ok", "service": "unrelated"}
    )[0]


def test_wrong_service_occupying_port_is_rejected(monkeypatch):
    monkeypatch.setattr(mac_runtime, "port_open", lambda _port: True)
    monkeypatch.setattr(
        mac_runtime,
        "request_json",
        lambda _url, _timeout: {"status": "ok", "service": "unrelated"},
    )

    result = mac_runtime.probe_service("service-desk", port=18123)

    assert result.state == "foreign"
    assert "unexpected health" in result.detail


def test_stale_pid_record_is_cleaned_without_error(tmp_path, monkeypatch):
    path = mac_runtime.pid_file("endpoint", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"pid": 999999, "role": "endpoint"}), encoding="utf-8")
    monkeypatch.setattr(mac_runtime, "process_identity", lambda _pid: None)

    result = mac_runtime.stop_role("endpoint", tmp_path)

    assert result.state == "stale"
    assert "nothing was killed" in result.detail
    assert not path.exists()


def test_stop_refuses_to_signal_unrelated_process(tmp_path, monkeypatch):
    path = mac_runtime.pid_file("endpoint", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "pid": os.getpid(),
        "role": "endpoint",
        "repository": str(mac_runtime.repository_root()),
        "started": "same-start-time",
    }), encoding="utf-8")
    monkeypatch.setattr(
        mac_runtime, "process_identity", lambda _pid: ("same-start-time", "pytest worker")
    )
    signalled = []
    monkeypatch.setattr(mac_runtime.os, "kill", lambda _pid, sig: signalled.append(sig))

    result = mac_runtime.stop_role("endpoint", tmp_path)

    assert result.state == "foreign"
    assert signalled == []
    assert not path.exists()


def test_shell_launchers_force_profile_and_never_use_broad_kills():
    demo_dir = mac_runtime.repository_root() / "scripts" / "demo"
    launch = (demo_dir / "launch_all_mac.sh").read_text(encoding="utf-8")
    stop = (demo_dir / "stop_all_mac.sh").read_text(encoding="utf-8")

    for setting in (
        "DEMO_MODE=1",
        "EXECUTOR=mock",
        "AGENT_MODE=deterministic",
        "RUNBOOK_STORE=ubuntu-26.04",
        "MONITORING_ENABLED=1",
        "MONITORING_URL=http://127.0.0.1:8001",
    ):
        assert setting in launch
    combined = launch + stop
    assert "killall" not in combined
    assert "pkill" not in combined
    assert "git pull" not in combined


def test_finder_wrappers_resolve_their_own_location():
    demo_dir = mac_runtime.repository_root() / "scripts" / "demo"
    for name in (
        "Autonomous IT Support Demo.command",
        "Stop Autonomous IT Support Demo.command",
    ):
        content = (demo_dir / name).read_text(encoding="utf-8")
        assert 'dirname -- "$0"' in content
        assert "/Users/" not in content
