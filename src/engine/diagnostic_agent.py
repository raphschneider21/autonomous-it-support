from ..executors.executor_interface import IExecutor
from ..safety.safety_validator import validate_command, is_allowed
from ..models import SafetyTier


def diagnose(category: str, executor: IExecutor) -> list[dict]:
    commands = _get_diagnostic_commands(category)
    results = []

    for cmd in commands:
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
