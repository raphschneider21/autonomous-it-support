import glob
import json
import os
import re
from .executor_interface import IExecutor
from ..demo.state import demo_endpoint

FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures")
FIXTURES_PATH = os.path.join(FIXTURES_DIR, "mock_outputs.json")


class MockExecutor(IExecutor):
    """Deterministic executor for local testing and the live demo.

    Static command -> output fixtures come from `fixtures/mock_outputs.json`.
    A small set of commands is *stateful* so the full incident lifecycle
    (service stop -> fix -> start -> verify running) can be demonstrated.
    """

    def __init__(self, endpoint_state=None):
        self.outputs = self._load_fixtures()
        self.service_state = {"spooler": "Stopped"}
        self.endpoint_state = endpoint_state or demo_endpoint

    def _load_fixtures(self) -> dict:
        """Load `mock_outputs.json`, then any per-platform `mock_outputs_*.json`.

        Fixtures are matched by substring in insertion order, so the base file
        is loaded first and keeps precedence; a platform file (for example
        `mock_outputs_ubuntu-26.04.json`) only adds commands the base file does
        not already answer.
        """
        outputs: dict = {}
        if os.path.exists(FIXTURES_PATH):
            with open(FIXTURES_PATH, "r") as f:
                outputs.update(json.load(f))

        for path in sorted(glob.glob(os.path.join(FIXTURES_DIR, "mock_outputs_*.json"))):
            with open(path, "r") as f:
                for command, result in json.load(f).items():
                    outputs.setdefault(command, result)
        return outputs

    def _service_output(self, name: str, state: str) -> dict:
        return {
            "exit_code": 0,
            "stdout": (
                f"Status   Name     DisplayName\n"
                f"------   ----     -----------\n"
                f"{state}     {name}   Print Spooler"
            ),
            "stderr": "",
        }

    def run(self, command: str, timeout: int = 30) -> dict:
        lower = re.sub(r"\s+", " ", command.lower()).strip()

        # Ubuntu hero scenario. Diagnostics, remediation and verification all
        # observe the same state object that Demo Lab mutates.
        endpoint_state = getattr(self, "endpoint_state", demo_endpoint)
        cups_result = endpoint_state.run_cups_command(lower)
        if cups_result is not None:
            return cups_result

        # Stateful print spooler lifecycle (overrides static fixtures)
        if "start-service -name spooler" in lower:
            self.service_state["spooler"] = "Running"
            return {"exit_code": 0, "stdout": "[MOCK] Service 'spooler' started successfully.", "stderr": ""}
        if "stop-service -name spooler" in lower:
            self.service_state["spooler"] = "Stopped"
            return {"exit_code": 0, "stdout": "[MOCK] Service 'spooler' stopped successfully.", "stderr": ""}
        if "get-service -name spooler" in lower:
            return self._service_output("spooler", self.service_state["spooler"])

        for pattern, result in self.outputs.items():
            if pattern.lower() in lower:
                return {
                    "exit_code": result.get("exit_code", 0),
                    "stdout": result.get("stdout", ""),
                    "stderr": result.get("stderr", ""),
                }
        return {
            "exit_code": 0,
            "stdout": f"[MOCK] No fixture for: {command}",
            "stderr": "",
        }
