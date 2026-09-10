"""Thread-safe simulated Ubuntu endpoint used by the graded demo.

This is deliberately in-memory.  A reset always returns the process to one
known baseline, and both Demo Lab and MockExecutor operate on this same object.
No method in this module invokes an operating-system command.
"""
from __future__ import annotations

from threading import RLock


ENDPOINT_NAME = "ubuntu-demo-01"

AVAILABLE_FAULTS = (
    {
        "id": "cups_stopped",
        "label": "CUPS printing service stopped",
        "category": "printing",
    },
)


class DemoEndpointState:
    """Small, explicit state machine for the canonical Ubuntu scenario."""

    def __init__(self) -> None:
        self._lock = RLock()
        self.reset()

    def reset(self) -> dict:
        """Restore the healthy baseline. Safe and idempotent."""
        with self._lock:
            self._cups = "active"
            self._print_queue = "empty"
            return self.snapshot()

    def inject_fault(self, fault_id: str) -> dict:
        """Apply a supported fault or raise KeyError for an unknown id."""
        with self._lock:
            if fault_id != "cups_stopped":
                raise KeyError(fault_id)
            self._cups = "inactive"
            return self.snapshot()

    def snapshot(self) -> dict:
        """Return the stable Demo Lab API representation."""
        with self._lock:
            active_faults = ["cups_stopped"] if self._cups == "inactive" else []
            return {
                "endpoint": ENDPOINT_NAME,
                "mode": "simulated",
                "available_faults": [dict(fault) for fault in AVAILABLE_FAULTS],
                "active_faults": active_faults,
                "services": {"cups": self._cups},
                "print_queue": self._print_queue,
            }

    def run_cups_command(self, command: str) -> dict | None:
        """Execute one supported CUPS command against simulated state.

        ``None`` means the command is unrelated and the executor should fall
        through to its ordinary fixtures.  The returned shape matches
        ``IExecutor.run``.
        """
        normalized = " ".join(command.lower().split())
        with self._lock:
            if normalized == "systemctl is-active cups":
                return {
                    "exit_code": 0 if self._cups == "active" else 3,
                    "stdout": self._cups,
                    "stderr": "",
                }
            if normalized == "sudo systemctl restart cups":
                self._cups = "active"
                return {
                    "exit_code": 0,
                    "stdout": "[MOCK] cups.service restarted; simulated state is active.",
                    "stderr": "",
                }
            if normalized == "cancel -a":
                self._print_queue = "empty"
                return {"exit_code": 0, "stdout": "", "stderr": ""}
            if normalized == "lpstat -o":
                stdout = "" if self._print_queue == "empty" else self._print_queue
                return {"exit_code": 0, "stdout": stdout, "stderr": ""}
        return None


demo_endpoint = DemoEndpointState()
