from scripts.demo import preflight
from scripts.demo.preflight import check_bind_available, check_environment
import pytest


def _safe_env(**overrides):
    env = {
        "DEMO_MODE": "1",
        "EXECUTOR": "mock",
        "AGENT_MODE": "deterministic",
        "MONITORING_ENABLED": "1",
        "MONITORING_URL": "http://10.0.0.2:8001",
    }
    env.update(overrides)
    return env


def test_preflight_accepts_the_frozen_demo_profile():
    assert all(check.ok for check in check_environment(_safe_env()))


def test_preflight_rejects_real_executor():
    checks = check_environment(_safe_env(EXECUTOR="real"))
    assert next(c for c in checks if c.name == "mock executor").ok is False


def test_preflight_rejects_live_model_path_even_without_a_key():
    checks = check_environment(_safe_env(AGENT_MODE="live"))
    assert next(c for c in checks if c.name == "deterministic agents").ok is False


def test_deterministic_mode_neutralizes_an_existing_external_key():
    checks = check_environment(_safe_env(ANTHROPIC_API_KEY="sk-ant-not-used"))
    deterministic = next(c for c in checks if c.name == "deterministic agents")
    assert deterministic.ok is True
    assert "present" in deterministic.detail


def _healthy_server(**overrides):
    health = {
        "endpoint": "ubuntu-demo-01",
        "executor": "mock",
        "executes_on_this_machine": False,
        "demo_mode": True,
        "agent_mode": "deterministic",
        "external_model_enabled": False,
        "requested_executor": "mock",
        "requested_agent_mode": "deterministic",
        "runbook_store": "ubuntu-26.04",
        "monitoring_enabled": True,
        "monitoring_reachable": True,
        "monitoring_url": "http://desk:8001",
    }
    health.update(overrides)
    return health


def _mock_services(monkeypatch, health=None, state_overrides=None, unreachable=False):
    health = health if health is not None else _healthy_server()
    state = {
        "endpoint": "ubuntu-demo-01",
        "mode": "simulated",
        "services": {"cups": "active"},
        "active_faults": [],
        "print_queue": "empty",
        "available_faults": [{"id": "cups_stopped"}],
    }
    state.update(state_overrides or {})
    calls = []

    def fake_request(url, method="GET", timeout=1.0):
        calls.append((url, method))
        if "/api/demo/" in url:
            return state
        if url.endswith("/api/runbooks"):
            return [{"id": "RB-CUPS-001"}]
        if url.startswith("http://desk:8001"):
            if unreachable:
                raise OSError("connection refused")
            return {"status": "ok", "service": "monitoring"}
        return health

    monkeypatch.setattr(preflight, "_request_json", fake_request)
    return calls


def test_preflight_reports_an_unreachable_service_desk(monkeypatch):
    _mock_services(monkeypatch, unreachable=True)
    checks = preflight.check_running_services("http://endpoint:8000")
    service_desk = next(c for c in checks if c.name == "Service Desk")
    assert service_desk.ok is False
    assert "connection refused" in service_desk.detail


def test_running_preflight_uses_server_configuration_and_checks_idempotent_reset(monkeypatch):
    monkeypatch.setenv("EXECUTOR", "real")  # Local shell is not the running service.
    calls = _mock_services(monkeypatch)
    checks = preflight.run_preflight("http://endpoint:8000")
    assert all(c.ok for c in checks)
    assert calls.count(("http://endpoint:8000/api/demo/reset", "POST")) == 2
    assert ("http://endpoint:8000/api/demo/state", "GET") in calls


@pytest.mark.parametrize("field,value", [
    ("executor", "real"), ("requested_executor", "real"),
    ("agent_mode", "live"), ("requested_agent_mode", "live"),
    ("demo_mode", False), ("runbook_store", "wrong-store"),
])
def test_running_preflight_rejects_unsafe_configuration_without_reset(monkeypatch, field, value):
    calls = _mock_services(monkeypatch, _healthy_server(**{field: value}))
    checks = preflight.check_running_services("http://endpoint:8000")
    assert not checks[0].ok
    assert not any(method == "POST" for _, method in calls)


def test_preflight_does_not_pass_when_endpoint_monitoring_is_disabled(monkeypatch):
    _mock_services(monkeypatch, _healthy_server(monitoring_enabled=False))
    checks = preflight.check_running_services("http://endpoint:8000")
    assert not next(c for c in checks if c.name == "endpoint monitoring").ok


def test_preflight_rejects_a_reset_that_does_not_restore_cups(monkeypatch):
    _mock_services(monkeypatch, state_overrides={"services": {"cups": "inactive"}})
    checks = preflight.check_running_services("http://endpoint:8000")
    assert not next(c for c in checks if c.name == "canonical reset").ok


def test_preflight_detects_an_occupied_endpoint_port(monkeypatch):
    class OccupiedSocket:
        def bind(self, address):
            raise OSError(48, "Address already in use")

        def close(self):
            pass

    monkeypatch.setattr(preflight.socket, "socket", lambda *args: OccupiedSocket())
    result = check_bind_available("http://127.0.0.1:8000")
    assert result.ok is False
    assert "unavailable" in result.detail
