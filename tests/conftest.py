"""Test-wide isolation from the live Claude API.

Once a developer exports `ANTHROPIC_API_KEY` — which is the whole point of
having one — every test that runs a full incident starts making real API calls.
That turns a 4-second suite into a multi-minute one, makes it depend on the
network, makes it non-deterministic, and quietly bills the team for running
`pytest`.

So the key is removed for every test by default. Tests that need to exercise
the Claude path install a fake client (see `test_llm_agents.py`), which is the
right way to assert request shape anyway.

A test that genuinely needs the live API opts in:

    @pytest.mark.live_api
    def test_something_against_the_real_model(): ...

and runs with `pytest -m live_api`. Those are excluded from a default run.
"""
import os

import pytest


def pytest_configure(config):
    config.addinivalue_line(
        "markers",
        "live_api: hits the real Anthropic API. Costs money, needs a key and a "
        "network. Excluded from a default run; use `pytest -m live_api`.",
    )


def pytest_collection_modifyitems(config, items):
    """Skip live-API tests unless they were asked for explicitly."""
    if config.getoption("-m") == "live_api":
        return
    skip = pytest.mark.skip(reason="live API test — run with `pytest -m live_api`")
    for item in items:
        if "live_api" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(autouse=True)
def _no_live_api(request, monkeypatch):
    """Remove the API key so no test can accidentally call Claude for real."""
    if "live_api" in request.keywords:
        yield
        return

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    # Runtime configuration from a developer's shell/.env must not select real
    # execution in engine tests, or disable the tests' explicitly fake clients.
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.setenv("AGENT_MODE", "auto")
    monkeypatch.setenv("EXECUTOR", "mock")

    from src.executors import factory
    from src.demo.state import demo_endpoint
    factory.reset_cache()
    demo_endpoint.reset()

    from src.engine import llm

    llm.reset_client()
    yield
    llm.reset_client()
    factory.reset_cache()
    demo_endpoint.reset()


@pytest.fixture(autouse=True)
def _no_live_monitoring(request, monkeypatch):
    """Point ticket reporting at a discard port unless a test opts in.

    Otherwise a developer running the real service desk on :8001 would have
    their dashboard filled with fixture incidents from a test run.
    """
    if "monitoring" in request.keywords or request.node.fspath.basename == "test_monitoring.py":
        yield
        return
    monkeypatch.setenv("MONITORING_ENABLED", "0")
    yield
