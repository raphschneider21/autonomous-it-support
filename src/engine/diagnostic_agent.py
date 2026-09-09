from ..executors.executor_interface import IExecutor
from ..safety.safety_validator import validate_command, is_allowed
from ..models import SafetyTier


def assess(diagnostics: list[dict], category: str) -> dict:
    """Build a structured root-cause assessment from diagnostic results.

    Used by the Incident Commander to detect disagreement between agents.
    """
    if diagnostics and any(d.get("exit_code") != 0 or "fail" in (d.get("stdout") or "").lower()
                          or "stopp" in (d.get("stdout") or "").lower()
                          or "error" in (d.get("stderr") or "").lower() for d in diagnostics):
        return {
            "agent": "DiagnosticAgent",
            "root_cause": f"infrastructure/{category}",
            "evidence": "Diagnostic output shows failures consistent with an endpoint infrastructure problem.",
        }

    return {
        "agent": "DiagnosticAgent",
        "root_cause": f"infrastructure/{category}",
        "evidence": "Diagnostic output shows the endpoint infrastructure responding normally.",
    }


def diagnose(category: str, executor: IExecutor) -> list[dict]:
    commands = _get_diagnostic_commands(category)
    # Deduplicate identical commands so we never run the same probe twice
    seen: set[str] = set()
    unique_commands = [c for c in commands if not (c in seen or seen.add(c))]
    results = []

    for cmd in unique_commands:
        tier = validate_command(cmd)
        if tier == SafetyTier.GREEN:
            output = executor.run(cmd)
            results.append({
                "command": cmd,
                "safety_tier": tier.value,
                "exit_code": output["exit_code"],
                "stdout": output["stdout"],
                "stderr": output["stderr"],
            })
        else:
            results.append({
                "command": cmd,
                "safety_tier": tier.value,
                "exit_code": -1,
                "stdout": "",
                "stderr": f"Blocked: {tier.value} tier command",
            })

    return results


def _get_diagnostic_commands(category: str) -> list[str]:
    commands = {
        "printer": [
            "Get-Service -Name spooler",
            "Get-ChildItem C:\\Windows\\System32\\spool\\PRINTERS",
            "Get-WinEvent -LogName System -MaxEvents 10 | Where-Object {$_.ProviderName -like '*Print*'}",
        ],
        "network": [
            "Test-NetConnection -ComputerName google.com -InformationLevel Detailed",
            "ipconfig /all",
            "Get-Service -Name Dnscache",
            "Get-NetAdapter | Select-Object Name, Status, LinkSpeed",
        ],
        "office": [
            "Get-Process | Where-Object {$_.ProcessName -like '*Teams*' -or $_.ProcessName -like '*Outlook*'}",
            "Get-ChildItem $env:APPDATA\\Microsoft\\Teams -ErrorAction SilentlyContinue",
        ],
        "frozen": [
            "Get-Process | Sort-Object CPU -Descending | Select-Object -First 10 Name, CPU, WorkingSet64",
            "Get-Counter '\\Processor(_Total)\\% Processor Time'",
        ],
        "legacy": [
            "Get-ItemProperty HKLM:\\Software\\Microsoft\\Windows\\CurrentVersion\\Run",
            "net use",
            "echo %PATH%",
        ],
    }
    return commands.get(category, ["Get-Service", "ipconfig"])
