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

def test_real_executor_runs_simple_command():
    executor = RealExecutor()
    result = executor.run("echo hello")
    assert result["exit_code"] == 0
    assert "hello" in result["stdout"]
    assert result["stderr"] == ""


def test_real_executor_captures_stderr():
    executor = RealExecutor()
    result = executor.run("python3 -c \"import sys; sys.stderr.write('err_msg')\"")
    assert result["exit_code"] == 0
    assert "err_msg" in result["stderr"]


def test_real_executor_nonzero_exit():
    executor = RealExecutor()
    result = executor.run("python3 -c \"exit(1)\"")
    assert result["exit_code"] == 1


def test_real_executor_timeout():
    executor = RealExecutor()
    result = executor.run("sleep 10", timeout=1)
    assert result["exit_code"] == -1
    assert "timed out" in result["stderr"].lower()


def test_real_executor_invalid_command():
    executor = RealExecutor()
    result = executor.run("nonexistent_command_xyz_12345")
    assert result["exit_code"] != 0
    assert result["stderr"] != ""


def test_real_executor_implements_interface():
    executor = RealExecutor()
    assert isinstance(executor, IExecutor)
