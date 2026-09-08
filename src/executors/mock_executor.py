import json
import os
import re
from .executor_interface import IExecutor

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "mock_outputs.json")


class MockExecutor(IExecutor):
    """Deterministic executor for local testing and the live demo.

    Static command -> output fixtures come from `fixtures/mock_outputs.json`.
    A small set of commands is *stateful* so the full incident lifecycle
    (service stop -> fix -> start -> verify running) can be demonstrated.
    """

    def __init__(self):
        self.outputs = self._load_fixtures()
        self.service_state = {"spooler": "Stopped"}

    def _load_fixtures(self) -> dict:
        if os.path.exists(FIXTURES_PATH):
            with open(FIXTURES_PATH, "r") as f:
                return json.load(f)
        return {}

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