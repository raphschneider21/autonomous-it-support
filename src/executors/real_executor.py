"""Executes commands on the real machine, without a shell.

Two properties matter here, and both are load-bearing:

1. **No shell.** The command is `shlex`-split and handed to `subprocess.run` as
   an argument list with `shell=False`. `;`, `|`, `&&`, `$()` and redirection
   are therefore inert — passed to the binary as literal arguments rather than
   interpreted. This is what turns the allowlist from the only line of defence
   into the second one.

2. **The executor re-checks.** Every command is classified again immediately
   before execution, even though the Incident Commander already classified it.
   A caller that forgets to check cannot make this class run something the
   allowlist denies.
"""
import subprocess

from ..safety.safety_validator import classify, split_command
from .executor_interface import IExecutor


class RealExecutor(IExecutor):
    """Runs allowlisted commands on the local system."""

    def run(self, command: str, timeout: int = 30) -> dict:
        decision = classify(command)

        if not decision.allowed:
            # Defence in depth. Reaching here means a caller skipped the gate;
            # the audit trail should show that it was stopped anyway.
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"REFUSED BY SAFETY LAYER: {decision.reason}",
                "refused": True,
            }

        try:
            argv = split_command(command)
        except ValueError as exc:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"REFUSED BY SAFETY LAYER: unparseable command ({exc}).",
                "refused": True,
            }

        try:
            result = subprocess.run(
                argv,
                shell=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
            return {
                "exit_code": result.returncode,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "refused": False,
            }
        except subprocess.TimeoutExpired:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command timed out after {timeout}s",
                "refused": False,
            }
        except FileNotFoundError:
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Command not found: {argv[0]}",
                "refused": False,
            }
        except Exception as exc:  # noqa: BLE001 - surfaced to the audit trail
            return {
                "exit_code": -1,
                "stdout": "",
                "stderr": str(exc),
                "refused": False,
            }
