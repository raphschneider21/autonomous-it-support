import os
import json
import tempfile
from src.executors.executor_interface import IExecutor
from src.executors.mock_executor import MockExecutor
from src.executors.real_executor import RealExecutor


# --- MockExecutor Tests ---

def test_mock_executor_returns_fixture_output():
    executor = MockExecutor()
    result = executor.run("Get-Service -Name spooler")
    assert result["exit_code"] == 0
    assert "Stopped" in result["stdout"]
    assert result["stderr"] == ""


def test_mock_executor_case_insensitive_match():
    executor = MockExecutor()
    result = executor.run("get-service -name spooler")
    assert result["exit_code"] == 0
    assert "spooler" in result["stdout"]


def test_mock_executor_partial_match():
    executor = MockExecutor()
    result = executor.run("ipconfig /all")
    assert result["exit_code"] == 0
    assert "192.168.1.100" in result["stdout"]


def test_mock_executor_no_fixture_returns_fallback():
    executor = MockExecutor()
    result = executor.run("SomeUnknownCommand -Flag")
    assert result["exit_code"] == 0
    assert "[MOCK]" in result["stdout"]
    assert result["stderr"] == ""


def test_mock_executor_flushdns_fixture():
    executor = MockExecutor()
    result = executor.run("ipconfig /flushdns")
    assert result["exit_code"] == 0
    assert "flushed" in result["stdout"].lower()


def test_mock_executor_implements_interface():
    executor = MockExecutor()
    assert isinstance(executor, IExecutor)


def test_mock_executor_custom_fixtures(tmp_path):
    fixtures = {
        "mycommand": {"exit_code": 42, "stdout": "custom out", "stderr": "custom err"}
    }
    fixture_file = tmp_path / "custom_fixtures.json"
    fixture_file.write_text(json.dumps(fixtures))

    executor = MockExecutor.__new__(MockExecutor)
    executor.outputs = fixtures

    result = executor.run("mycommand")
    assert result["exit_code"] == 42
    assert result["stdout"] == "custom out"
    assert result["stderr"] == "custom err"


# --- RealExecutor Tests ---
#
# RealExecutor no longer runs a shell and refuses anything the allowlist denies.
# The old tests here drove it with `echo hello`, `sleep 10` and `python3 -c ...`
# — none of which are allowlisted, and `python3` is explicitly forbidden because
# it is arbitrary code execution. They were testing that a shell ran, which is
# the property we deliberately removed.


def test_real_executor_runs_an_allowlisted_command():
    result = RealExecutor().run("uname -a")
    assert result["exit_code"] == 0
    assert result["stdout"].strip()
    assert result["refused"] is False


def test_real_executor_refuses_a_denied_command():
    """The executor re-checks, so a caller that skips the gate still cannot run this."""
    result = RealExecutor().run("rm -rf /")
    assert result["refused"] is True
    assert result["exit_code"] == -1
    assert "REFUSED BY SAFETY LAYER" in result["stderr"]


def test_real_executor_refuses_a_chained_payload():
    result = RealExecutor().run("df -h; cat /etc/shadow")
    assert result["refused"] is True
    assert result["stdout"] == ""


def test_real_executor_never_invokes_a_shell(monkeypatch):
    """The property that makes metacharacters inert. Asserted directly."""
    seen = {}

    class _Completed:
        returncode, stdout, stderr = 0, "", ""

    def fake_run(argv, **kwargs):
        seen["argv"] = argv
        seen["kwargs"] = kwargs
        return _Completed()

    monkeypatch.setattr("src.executors.real_executor.subprocess.run", fake_run)
    RealExecutor().run("df -h /")

    assert isinstance(seen["argv"], list), "command must be an argument list, not a string"
    assert seen["argv"] == ["df", "-h", "/"]
    assert seen["kwargs"]["shell"] is False


def test_real_executor_timeout(monkeypatch):
    import subprocess

    def fake_run(*a, **kw):
        raise subprocess.TimeoutExpired(cmd="uname", timeout=1)

    monkeypatch.setattr("src.executors.real_executor.subprocess.run", fake_run)
    result = RealExecutor().run("uname -a", timeout=1)
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()


def test_real_executor_missing_binary(monkeypatch):
    def fake_run(*a, **kw):
        raise FileNotFoundError()

    monkeypatch.setattr("src.executors.real_executor.subprocess.run", fake_run)
    result = RealExecutor().run("systemctl is-active nginx")
    assert result["exit_code"] == -1
    assert "not found" in result["stderr"].lower()


def test_real_executor_implements_interface():
    assert isinstance(RealExecutor(), IExecutor)
