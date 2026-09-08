import subprocess
from .executor_interface import IExecutor


class RealExecutor(IExecutor):
    def run(self, command: str, timeout: int = 30) -> dict:
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
            }
        except subprocess.TimeoutExpired:
            return {"exit_code": -1, "stdout": "", "stderr": "Command timed out"}
        except Exception as e:
            return {"exit_code": -1, "stdout": "", "stderr": str(e)}
