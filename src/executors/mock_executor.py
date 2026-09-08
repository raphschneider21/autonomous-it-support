import json
import os
from .executor_interface import IExecutor

FIXTURES_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "fixtures", "mock_outputs.json")


class MockExecutor(IExecutor):
    def __init__(self):
        self.outputs = self._load_fixtures()

    def _load_fixtures(self) -> dict:
        if os.path.exists(FIXTURES_PATH):
            with open(FIXTURES_PATH, "r") as f:
                return json.load(f)
        return {}

    def run(self, command: str, timeout: int = 30) -> dict:
        for pattern, result in self.outputs.items():
            if pattern.lower() in command.lower():
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
