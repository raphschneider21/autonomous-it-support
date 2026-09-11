#!/usr/bin/env python3
"""Cross-platform runtime helper for the macOS and Windows demo launchers.

Only standard-library modules are imported for probing and process management.
PID records bind a process ID to its start time, command, repository, and role,
so a reused PID can never cause an unrelated process to be terminated.
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


HOST = "127.0.0.1"
ROLES = {
    "endpoint": {"port": 8000, "service": "Endpoint runtime"},
    "service-desk": {"port": 8001, "service": "Service Desk"},
}
PROBE_EXPECTED = 0
PROBE_FREE = 10
PROBE_FOREIGN = 20


@dataclass(frozen=True)
class Probe:
    state: str
    detail: str


@dataclass(frozen=True)
class StopResult:
    state: str
    detail: str


def repository_root() -> Path:
    return Path(__file__).resolve().parents[2]


def runtime_root(value: str | None = None) -> Path:
    configured = value or os.environ.get("DEMO_RUNTIME_DIR")
    return Path(configured).expanduser().resolve() if configured else repository_root() / ".demo-runtime"


def role_port(role: str) -> int:
    return int(ROLES[role]["port"])


def health_url(role: str, port: int | None = None) -> str:
    return f"http://{HOST}:{port or role_port(role)}/api/health"


def _request(url: str, timeout: float = 1.0) -> tuple[int, str, str]:
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, response.headers.get("content-type", ""), response.read().decode("utf-8")


def request_json(url: str, timeout: float = 1.0) -> dict[str, Any] | list[Any]:
    status, _, body = _request(url, timeout)
    if not 200 <= status < 300:
        raise RuntimeError(f"HTTP {status}")
    return json.loads(body)


def validate_health(role: str, payload: Any) -> tuple[bool, str]:
    if not isinstance(payload, dict):
        return False, "health response is not an object"
    if role == "service-desk":
        ok = payload.get("status") == "ok" and payload.get("service") == "monitoring"
        return ok, "Service Desk health identified" if ok else f"unexpected health: {payload}"

    required = {
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
    mismatches = [f"{key}={payload.get(key)!r} (expected {expected!r})"
                  for key, expected in required.items() if payload.get(key) != expected]
    return (not mismatches, "safe deterministic endpoint health verified" if not mismatches
            else "; ".join(mismatches))


def port_open(port: int, host: str = HOST, timeout: float = 0.2) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def probe_service(role: str, port: int | None = None, timeout: float = 0.7) -> Probe:
    port = port or role_port(role)
    if not port_open(port):
        return Probe("free", f"{HOST}:{port} is available")
    try:
        payload = request_json(health_url(role, port), timeout)
    except Exception as exc:  # noqa: BLE001 - diagnostic boundary
        return Probe("foreign", f"{HOST}:{port} is occupied but expected health failed: {exc}")
    ok, detail = validate_health(role, payload)
    return Probe("expected" if ok else "foreign", detail)


def wait_for_service(role: str, timeout: float = 20.0) -> Probe:
    deadline = time.monotonic() + timeout
    last_detail = "service has not started listening"
    while time.monotonic() < deadline:
        try:
            payload = request_json(health_url(role), timeout=0.7)
            ok, detail = validate_health(role, payload)
            if ok:
                return Probe("expected", detail)
            return Probe("foreign", detail)
        except Exception as exc:  # noqa: BLE001 - startup can be briefly unavailable
            last_detail = str(exc)
            time.sleep(0.2)
    return Probe("timeout", f"health did not become ready: {last_detail}")


def check_presentation_surfaces() -> list[tuple[str, bool, str]]:
    checks = []
    pages = (
        ("Employee Support", "http://127.0.0.1:8000/", "IT Support Assistant"),
        ("Demo Lab", "http://127.0.0.1:8000/static/demo.html", "Demo Lab"),
        ("Service Desk", "http://127.0.0.1:8001/", "IT Service Desk"),
    )
    for name, url, marker in pages:
        try:
            status, content_type, body = _request(url, timeout=1.5)
            ok = status == 200 and "text/html" in content_type and marker in body
            checks.append((name, ok, f"{url} returned {status}" if ok else f"unexpected response from {url}"))
        except Exception as exc:  # noqa: BLE001
            checks.append((name, False, f"{url}: {exc}"))
    try:
        state = request_json("http://127.0.0.1:8000/api/demo/state", timeout=1.5)
        ok = (isinstance(state, dict) and state.get("endpoint") == "ubuntu-demo-01"
              and state.get("mode") == "simulated")
        checks.append(("Demo Lab API", ok, "simulated endpoint state available" if ok else str(state)))
    except Exception as exc:  # noqa: BLE001
        checks.append(("Demo Lab API", False, str(exc)))
    return checks


def process_exists(pid: int) -> bool:
    if os.name == "nt":
        return _windows_process_identity(pid) is not None
    try:
        os.kill(pid, 0)
        return True
    except PermissionError:
        return True
    except (ProcessLookupError, OSError):
        return False


def _windows_process_identity(pid: int) -> tuple[str, str] | None:
    """Return an immutable creation timestamp and executable image path.

    Querying Win32_Process through CIM can require permissions that ordinary
    Windows accounts do not have. PROCESS_QUERY_LIMITED_INFORMATION is the
    least-privilege native API intended for this identity check.
    """
    import ctypes
    from ctypes import wintypes

    class FileTime(ctypes.Structure):
        _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))

    process_query_limited_information = 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(FileTime), ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime), ctypes.POINTER(FileTime),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        return None
    try:
        created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
        if not kernel32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel), ctypes.byref(user),
        ):
            return None
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        if not kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size)):
            return None
        started = f"{created.high:08x}{created.low:08x}"
        return started, image.value
    finally:
        kernel32.CloseHandle(handle)


def process_identity(pid: int) -> tuple[str, str] | None:
    if os.name == "nt":
        return _windows_process_identity(pid)
    if not process_exists(pid):
        return None
    try:
        started = subprocess.run(
            ["ps", "-p", str(pid), "-o", "lstart="], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        command = subprocess.run(
            ["ps", "-p", str(pid), "-o", "command="], check=True,
            capture_output=True, text=True,
        ).stdout.strip()
        return started, command
    except (OSError, subprocess.CalledProcessError):
        return None


def pid_file(role: str, root: Path) -> Path:
    return root / "pids" / f"{role}.json"


def write_pid_record(role: str, pid: int, root: Path) -> Path:
    identity = process_identity(pid)
    if identity is None:
        raise RuntimeError(f"process {pid} is not running or its identity could not be read")
    started, command = identity
    record = {
        "pid": pid,
        "role": role,
        "repository": str(repository_root()),
        "started": started,
        "command": command,
    }
    path = pid_file(role, root)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    os.replace(temporary, path)
    return path


def _command_contains(command: str, marker: str) -> bool:
    return marker.casefold() in command.casefold() if os.name == "nt" else marker in command


def _owned_process(record: dict[str, Any], role: str) -> tuple[bool, str]:
    try:
        pid = int(record["pid"])
    except (KeyError, TypeError, ValueError):
        return False, "PID record is invalid"
    identity = process_identity(pid)
    if identity is None:
        return False, "recorded process is no longer running"
    started, command = identity
    matches_identity = (
        record.get("role") == role
        and Path(str(record.get("repository", ""))).resolve() == repository_root()
        and record.get("started") == started
        and record.get("command") == command
    )
    if os.name == "nt":
        # The creation FILETIME prevents PID-reuse mistakes; the exact image
        # path additionally prevents a different executable from being owned.
        matches = matches_identity
    else:
        helper_marker = str(Path(__file__).resolve())
        expected_role = f"--role {role}"
        matches = (
            matches_identity
            and _command_contains(command, helper_marker)
            and " run " in f" {command} "
            and expected_role in command
        )
    return matches, "launcher-owned process verified" if matches else "PID now belongs to a different process"


def terminate_process(pid: int, expected_identity: tuple[str, str] | None = None) -> None:
    if os.name != "nt":
        os.kill(pid, signal.SIGTERM)
        return

    import ctypes
    from ctypes import wintypes

    class FileTime(ctypes.Structure):
        _fields_ = (("low", wintypes.DWORD), ("high", wintypes.DWORD))

    process_terminate_and_query = 0x0001 | 0x1000
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
    kernel32.OpenProcess.restype = wintypes.HANDLE
    kernel32.GetProcessTimes.argtypes = (
        wintypes.HANDLE, ctypes.POINTER(FileTime), ctypes.POINTER(FileTime),
        ctypes.POINTER(FileTime), ctypes.POINTER(FileTime),
    )
    kernel32.GetProcessTimes.restype = wintypes.BOOL
    kernel32.QueryFullProcessImageNameW.argtypes = (
        wintypes.HANDLE, wintypes.DWORD, wintypes.LPWSTR, ctypes.POINTER(wintypes.DWORD),
    )
    kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
    kernel32.TerminateProcess.argtypes = (wintypes.HANDLE, wintypes.UINT)
    kernel32.TerminateProcess.restype = wintypes.BOOL
    kernel32.CloseHandle.argtypes = (wintypes.HANDLE,)
    kernel32.CloseHandle.restype = wintypes.BOOL
    handle = kernel32.OpenProcess(process_terminate_and_query, False, pid)
    if not handle:
        raise PermissionError(ctypes.get_last_error(), f"cannot open owned PID {pid} for termination")
    try:
        created, exited, kernel, user = FileTime(), FileTime(), FileTime(), FileTime()
        size = wintypes.DWORD(32768)
        image = ctypes.create_unicode_buffer(size.value)
        identity_ok = kernel32.GetProcessTimes(
            handle, ctypes.byref(created), ctypes.byref(exited),
            ctypes.byref(kernel), ctypes.byref(user),
        ) and kernel32.QueryFullProcessImageNameW(handle, 0, image, ctypes.byref(size))
        actual_identity = (f"{created.high:08x}{created.low:08x}", image.value)
        if not identity_ok or expected_identity != actual_identity:
            raise RuntimeError(f"owned PID {pid} changed identity before termination; nothing was killed")
        if not kernel32.TerminateProcess(handle, 0):
            raise PermissionError(ctypes.get_last_error(), f"cannot terminate owned PID {pid}")
    finally:
        kernel32.CloseHandle(handle)


def stop_role(role: str, root: Path, timeout: float = 8.0) -> StopResult:
    path = pid_file(role, root)
    if not path.exists():
        return StopResult("not-running", "no launcher PID record")
    try:
        record = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        path.unlink(missing_ok=True)
        return StopResult("stale", f"invalid PID record removed: {exc}")

    owned, detail = _owned_process(record, role)
    if not owned:
        path.unlink(missing_ok=True)
        state = "stale" if detail == "recorded process is no longer running" else "foreign"
        return StopResult(state, f"{detail}; nothing was killed")

    pid = int(record["pid"])
    terminate_process(pid, (str(record["started"]), str(record["command"])))
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if not process_exists(pid):
            path.unlink(missing_ok=True)
            return StopResult("stopped", f"PID {pid} stopped")
        time.sleep(0.1)
    return StopResult("timeout", f"PID {pid} did not stop after SIGTERM; left for manual inspection")


def run_service(role: str) -> int:
    os.chdir(repository_root())
    sys.path.insert(0, str(repository_root()))
    import uvicorn

    if role == "service-desk":
        from src.monitoring.app import app
    else:
        from src.main import app
    uvicorn.run(app, host=HOST, port=role_port(role), log_level="info", access_log=False)
    return 0


def start_service(role: str, root: Path, log_file: Path) -> int:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    creationflags = 0
    popen_options: dict[str, Any] = {}
    if os.name == "nt":
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS
    else:
        popen_options["start_new_session"] = True
    with log_file.open("a", encoding="utf-8") as log:
        log.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting {ROLES[role]['service']}\n")
        log.flush()
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), "run", "--role", role],
            cwd=repository_root(), stdout=log, stderr=subprocess.STDOUT,
            creationflags=creationflags, **popen_options,
        )
    try:
        write_pid_record(role, process.pid, root)
    except Exception:
        if process.poll() is None:
            process.terminate()
        raise
    return process.pid


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("probe", "wait", "run", "start", "record", "stop"):
        command = sub.add_parser(name)
        command.add_argument("--role", required=True, choices=ROLES)
        if name == "wait":
            command.add_argument("--timeout", type=float, default=20.0)
        if name == "start":
            command.add_argument("--log-file", required=True)
        if name == "record":
            command.add_argument("--pid", required=True, type=int)
        if name in ("start", "record", "stop"):
            command.add_argument("--runtime-dir")
    sub.add_parser("check-surfaces")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command == "run":
        return run_service(args.role)
    if args.command == "probe":
        result = probe_service(args.role)
        print(f"{result.state.upper()}: {result.detail}")
        return {"expected": PROBE_EXPECTED, "free": PROBE_FREE}.get(result.state, PROBE_FOREIGN)
    if args.command == "wait":
        result = wait_for_service(args.role, args.timeout)
        print(f"{result.state.upper()}: {result.detail}")
        return 0 if result.state == "expected" else 1
    if args.command == "start":
        pid = start_service(args.role, runtime_root(args.runtime_dir), Path(args.log_file).resolve())
        print(pid)
        return 0
    if args.command == "record":
        path = write_pid_record(args.role, args.pid, runtime_root(args.runtime_dir))
        print(path)
        return 0
    if args.command == "stop":
        result = stop_role(args.role, runtime_root(args.runtime_dir))
        print(f"{result.state.upper()}: {result.detail}")
        return 1 if result.state == "timeout" else 0
    if args.command == "check-surfaces":
        checks = check_presentation_surfaces()
        for name, ok, detail in checks:
            print(f"[{'PASS' if ok else 'FAIL'}] {name}: {detail}")
        return 0 if all(ok for _, ok, _ in checks) else 1
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
