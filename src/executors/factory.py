"""Chooses the executor, and makes the choice impossible to miss.

`EXECUTOR=mock` (the default) returns fixture output. `EXECUTOR=real` runs the
commands on this machine.

The default is mock deliberately: a checkout that has just been cloned onto a
new machine should not start issuing `systemctl` commands because someone
forgot to read the README. Opting in to real execution is a decision, not an
accident.

The failure mode this module exists to prevent is the quiet one. Mock and real
runs look *identical* in the UI — the same "Executed: …" events, the same
"Verification passed" — so a demo on a real VM can appear to fix a real fault
while touching nothing at all. `active_executor_name()` is surfaced on
`/api/health` and logged at startup so the mode is always visible somewhere.
"""
import os

from .. import config
from .executor_interface import IExecutor
from .mock_executor import MockExecutor
from .real_executor import RealExecutor

MOCK = "mock"
REAL = "real"

_instances: dict[str, IExecutor] = {}


def active_executor_name() -> str:
    """Which executor the engine will use, from the environment."""
    choice = requested_executor_name()
    if config.demo_mode_enabled():
        return MOCK
    return REAL if choice == REAL else MOCK


def requested_executor_name() -> str:
    """Raw executor request, kept visible when demo mode safely overrides it."""
    return os.environ.get("EXECUTOR", MOCK).strip().lower() or MOCK


def get_executor() -> IExecutor:
    """The executor for this run.

    Resolved per call rather than at import, so a test or a restart can change
    the mode without reloading the module. Instances are cached because
    MockExecutor holds fixture state across a run.
    """
    name = active_executor_name()
    if name not in _instances:
        _instances[name] = RealExecutor() if name == REAL else MockExecutor()
    return _instances[name]


def is_real() -> bool:
    return active_executor_name() == REAL


def describe() -> dict:
    """Executor mode, for /api/health and the startup banner."""
    real = is_real()
    safety_override = config.demo_mode_enabled() and requested_executor_name() == REAL
    return {
        "executor": active_executor_name(),
        "requested_executor": requested_executor_name(),
        "demo_safety_override": safety_override,
        "executes_on_this_machine": real,
        "note": (
            "DEMO_MODE forced the MockExecutor because EXECUTOR=real was requested. "
            "Nothing on this machine is touched. Disable demo mode deliberately "
            "before using the optional real executor."
            if safety_override else
            "Commands run on this machine. Every one is checked against the "
            "allowlist first, and anything unrecognised is refused."
            if real else
            "Commands use simulated endpoint state and recorded fixture output. "
            "Nothing on this machine is touched. Real execution requires "
            "DEMO_MODE=0 and EXECUTOR=real."
        ),
    }


def reset_cache() -> None:
    """Test hook: drop cached instances so the mode can be switched."""
    _instances.clear()
