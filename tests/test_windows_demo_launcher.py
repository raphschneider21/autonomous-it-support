"""Cross-platform tests for the Windows one-click demo launcher."""
from __future__ import annotations

import json
import os

from scripts.demo import demo_runtime


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


def test_shared_repository_root_resolves_from_helper_location():
    root = demo_runtime.repository_root()
    assert (root / "src" / "main.py").is_file()
    assert (root / "scripts" / "demo" / "launch_all_windows.ps1").is_file()


def test_safe_configuration_requires_every_runtime_boundary():
    assert demo_runtime.validate_health("endpoint", SAFE_ENDPOINT_HEALTH)[0]
    for field, unsafe in (
        ("endpoint", "windows-host"),
        ("executor", "real"),
        ("demo_mode", False),
        ("agent_mode", "live"),
        ("external_model_enabled", True),
        ("monitoring_reachable", False),
    ):
        accepted, reason = demo_runtime.validate_health(
            "endpoint", {**SAFE_ENDPOINT_HEALTH, field: unsafe}
        )
        assert not accepted
        assert field in reason


def test_wrong_service_occupying_port_is_rejected(monkeypatch):
    monkeypatch.setattr(demo_runtime, "port_open", lambda _port: True)
    monkeypatch.setattr(
        demo_runtime,
        "request_json",
        lambda _url, _timeout: {"status": "ok", "service": "unrelated"},
    )
    result = demo_runtime.probe_service("service-desk", port=18123)
    assert result.state == "foreign"
    assert "unexpected health" in result.detail


def test_stale_pid_record_is_cleaned_without_signalling(tmp_path, monkeypatch):
    path = demo_runtime.pid_file("endpoint", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"pid": 999999, "role": "endpoint"}), encoding="utf-8")
    monkeypatch.setattr(demo_runtime, "process_identity", lambda _pid: None)
    terminations = []
    monkeypatch.setattr(
        demo_runtime, "terminate_process", lambda pid, identity: terminations.append((pid, identity))
    )

    result = demo_runtime.stop_role("endpoint", tmp_path)

    assert result.state == "stale"
    assert terminations == []
    assert not path.exists()


def test_ownership_validation_requires_recorded_command(tmp_path, monkeypatch):
    path = demo_runtime.pid_file("endpoint", tmp_path)
    path.parent.mkdir(parents=True)
    helper = str(demo_runtime.Path(demo_runtime.__file__).resolve())
    recorded_command = f'python "{helper}" run --role endpoint'
    path.write_text(json.dumps({
        "pid": os.getpid(),
        "role": "endpoint",
        "repository": str(demo_runtime.repository_root()),
        "started": "same-start-time",
        "command": recorded_command,
    }), encoding="utf-8")
    monkeypatch.setattr(
        demo_runtime,
        "process_identity",
        lambda _pid: ("same-start-time", recorded_command + " --changed"),
    )
    terminations = []
    monkeypatch.setattr(
        demo_runtime, "terminate_process", lambda pid, identity: terminations.append((pid, identity))
    )

    result = demo_runtime.stop_role("endpoint", tmp_path)

    assert result.state == "foreign"
    assert terminations == []
    assert not path.exists()


def test_stop_never_targets_unrelated_process(tmp_path, monkeypatch):
    path = demo_runtime.pid_file("service-desk", tmp_path)
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({
        "pid": os.getpid(),
        "role": "service-desk",
        "repository": str(demo_runtime.repository_root()),
        "started": "same-start-time",
        "command": "python unrelated.py",
    }), encoding="utf-8")
    monkeypatch.setattr(
        demo_runtime, "process_identity", lambda _pid: ("reused-pid-start-time", "python unrelated.py")
    )
    terminations = []
    monkeypatch.setattr(
        demo_runtime, "terminate_process", lambda pid, identity: terminations.append((pid, identity))
    )

    result = demo_runtime.stop_role("service-desk", tmp_path)

    assert result.state == "foreign"
    assert terminations == []


def test_owned_process_is_terminated_with_its_recorded_identity(tmp_path, monkeypatch):
    path = demo_runtime.pid_file("endpoint", tmp_path)
    path.parent.mkdir(parents=True)
    if os.name == "nt":
        command = r"C:\Python\python.exe"
    else:
        command = f"python {demo_runtime.Path(demo_runtime.__file__).resolve()} run --role endpoint"
    identity = ("recorded-start-time", command)
    path.write_text(json.dumps({
        "pid": 4242,
        "role": "endpoint",
        "repository": str(demo_runtime.repository_root()),
        "started": identity[0],
        "command": identity[1],
    }), encoding="utf-8")
    monkeypatch.setattr(demo_runtime, "process_identity", lambda _pid: identity)
    terminations = []
    monkeypatch.setattr(
        demo_runtime, "terminate_process", lambda pid, expected: terminations.append((pid, expected))
    )
    monkeypatch.setattr(demo_runtime, "process_exists", lambda _pid: False)

    result = demo_runtime.stop_role("endpoint", tmp_path)

    assert result.state == "stopped"
    assert terminations == [(4242, identity)]
    assert not path.exists()


def test_windows_launchers_force_profile_and_have_no_broad_process_kill():
    demo_dir = demo_runtime.repository_root() / "scripts" / "demo"
    launch = (demo_dir / "launch_all_windows.ps1").read_text(encoding="utf-8")
    stop = (demo_dir / "stop_all_windows.ps1").read_text(encoding="utf-8")
    combined = (launch + stop).casefold()

    for setting in (
        '$env:DEMO_MODE = "1"',
        '$env:EXECUTOR = "mock"',
        '$env:AGENT_MODE = "deterministic"',
        '$env:RUNBOOK_STORE = "ubuntu-26.04"',
        '$env:MONITORING_ENABLED = "1"',
        '$env:MONITORING_URL = "http://127.0.0.1:8001"',
        '$env:ENDPOINT_NAME = "ubuntu-demo-01"',
    ):
        assert setting in launch
    assert "taskkill" not in combined
    assert "stop-process" not in combined
    assert "/im python" not in combined
    assert "git pull" not in combined


def test_cmd_wrappers_are_location_relative_and_policy_is_process_local():
    demo_dir = demo_runtime.repository_root() / "scripts" / "demo"
    launch = (demo_dir / "Autonomous IT Support Demo.cmd").read_text(encoding="utf-8")
    stop = (demo_dir / "Stop Autonomous IT Support Demo.cmd").read_text(encoding="utf-8")
    for content in (launch, stop):
        assert "%~dp0" in content
        assert "-ExecutionPolicy Bypass" in content
        assert "Set-ExecutionPolicy" not in content
        assert "C:\\Users\\" not in content
