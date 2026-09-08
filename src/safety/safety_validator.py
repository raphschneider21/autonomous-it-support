from ..models import SafetyTier

# Green: auto-execute (read-only diagnostics)
GREEN_COMMANDS = [
    "get-service",
    "get-winevent",
    "test-netconnection",
    "ping",
    "ipconfig",
    "ipconfig /all",
    "systemctl status",
    "journalctl",
    "ps aux",
    "df -h",
    "netstat",
    "cat /etc/resolv.conf",
    "ls",
    "pwd",
]

# Yellow: requires human approval (state-altering)
YELLOW_COMMANDS = [
    "stop-service",
    "start-service",
    "restart-service",
    "ipconfig /flushdns",
    "ipconfig /renew",
    "remove-item",
    "clear-recyclebin",
    "klist purge",
    "netsh",
    "systemctl restart",
    "systemctl stop",
    "kill",
    "pkill",
]

# Red: hard blocked (never allowed)
RED_COMMANDS = [
    "remove-item -path c:\\windows",
    "format",
    "rd /s",
    "rmdir /s",
    "net user",
    "net localgroup administrators",
    "disable-service",
    "stop-computer",
    "shutdown",
    "bcdedit",
    "cipher /w",
    "takeown",
    "icacls",
    "advfirewall",
    "disable firewall",
    "disable antivirus",
]


def validate_command(command: str) -> SafetyTier:
    cmd_lower = command.lower().strip()

    for pattern in RED_COMMANDS:
        if pattern in cmd_lower:
            return SafetyTier.RED

    for pattern in YELLOW_COMMANDS:
        if pattern in cmd_lower:
            return SafetyTier.YELLOW

    return SafetyTier.GREEN


def is_allowed(command: str) -> bool:
    return validate_command(command) != SafetyTier.RED
