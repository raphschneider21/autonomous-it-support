"""Regression tests for the Windows one-click demo launcher."""
from __future__ import annotations

import json
from types import SimpleNamespace

from scripts.demo import mac_runtime


def test_windows_launchers_exist_and_resolve_from_own_location():
    demo_dir = mac_runtime.repository_root() / "scripts" / "demo"
    for name in (
        "Autonomous IT Support Demo.cmd",
        "Stop Autonomous IT Support Demo.cmd",
        "launch_all_windows.ps1",
        "stop_all_windows.ps1",
    ):
        assert (demo_dir / name).is_file()

    for name in ("Autonomous IT Support Demo.cmd", "Stop Autonomous IT Support Demo.cmd"):
        text = (demo_dir / name).read_text(encoding="utf-8")
        assert "%~dp0" in text
        assert "powershell.exe" in text
        assert "C:\\Users\\" not in text


def test_windows_launcher_forces_safe_graded_profile():
    launch = (
        mac_runtime.repository_root() / "scripts" / "demo" / "launch_all_windows.ps1"
    ).read_text(encoding="utf-8")

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

    assert "preflight.py" in launch
    assert "check-surfaces" in launch
    assert "DEMO READY" in launch
    assert "git pull" not in launch


def test_windows_stop_path_never_uses_broad_process_kills():
    demo_dir = mac_runtime.repository_root() / "scripts" / "demo"
    stop = (demo_dir / "stop_all_windows.ps1").read_text(encoding="utf-8")
    helper = (demo_dir / "mac_runtime.py").read_text(encoding="utf-8")

    combined = stop + helper
    assert "taskkill /IM" not in combined
    assert "Stop-Process -Name" not in combined
    assert "killall" not in combined
    assert "pkill" not in combined
    assert '["taskkill", "/PID", str(pid), "/T", "/F"]' in helper


def test_windows_process_identity_parses_cim_result(monkeypatch):
    payload = {
        "started": "2026-09-11T09:15:22.0000000Z",
        "command": '"C:\\Python\\python.exe" "C:\\repo\\scripts\\demo\\mac_runtime.py" run --role endpoint',
    }

    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=0, stdout=json.dumps(payload), stderr="")

    monkeypatch.setattr(mac_runtime.subprocess, "run", fake_run)
    assert mac_runtime._windows_process_identity(1234) == (
        payload["started"], payload["command"]
    )


def test_windows_process_identity_returns_none_when_pid_missing(monkeypatch):
    def fake_run(*_args, **_kwargs):
        return SimpleNamespace(returncode=3, stdout="", stderr="")

    monkeypatch.setattr(mac_runtime.subprocess, "run", fake_run)
    assert mac_runtime._windows_process_identity(999999) is None


def test_windows_cmd_wrappers_do_not_require_admin():
    demo_dir = mac_runtime.repository_root() / "scripts" / "demo"
    for name in ("Autonomous IT Support Demo.cmd", "Stop Autonomous IT Support Demo.cmd"):
        text = (demo_dir / name).read_text(encoding="utf-8").lower()
        assert "runas" not in text
        assert "start-process -verb runas" not in text
