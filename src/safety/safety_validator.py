import re

from ..models import SafetyTier

# Green: auto-execute (read-only diagnostics)
GREEN_COMMANDS = [
    # --- Windows / PowerShell ---
    "get-service",
    "get-winevent",
    "test-netconnection",
    "ping",
    "ipconfig",
    "ipconfig /all",
    "netstat",
    "ls",
    "pwd",
    # --- Ubuntu 26.04: read-only service and system state ---
    "systemctl status",
    "systemctl is-active",
    "systemctl --user is-active",
    "journalctl",
    "ps aux",
    "ps -eo",
    "pgrep",
    "lsmod",
    "lsblk",
    "findmnt",
    "df -h",
    "du -sh",
    "free -h",
    "uname -a",
    "cat /etc/resolv.conf",
    "cat /etc/networkmanager",
    # --- Ubuntu 26.04: read-only subsystem queries ---
    "resolvectl status",
    "resolvectl query",
    "timedatectl status",
    "timedatectl show",
    "timedatectl list-timezones",
    "rfkill list",
    "nmcli -t -f",
    "nmcli general status",
    "nmcli device status",
    "bluetoothctl show",
    "wpctl status",
    "wpctl get-volume",
    "pactl info",
    "pactl list",
    "amixer -d pulse sget",
    "gsettings get",
    "gdctl show",
    "brightnessctl info",
    "libinput list-devices",
    "xinput list",
    "lpstat",
    "apt-cache policy",
    "apt list --upgradable",
    "busctl --user call",
    # Read-only checks that still need root to open their state files. Listed
    # explicitly so they stay auto-approved despite the `sudo` rule below.
    "sudo apt-get check",
    "sudo dpkg --audit",
    "sudo fuser",
]

# Yellow: requires human approval (state-altering)
YELLOW_COMMANDS = [
    # --- Windows / PowerShell ---
    "stop-service",
    "start-service",
    "restart-service",
    "ipconfig /flushdns",
    "ipconfig /renew",
    "remove-item",
    "clear-recyclebin",
    "klist purge",
    "netsh",
    # Any elevation is a state change until proven otherwise. Read-only `sudo`
    # diagnostics are listed in GREEN_COMMANDS and win on specificity.
    "sudo",
    # --- Ubuntu 26.04: service lifecycle ---
    "systemctl restart",
    "systemctl stop",
    "systemctl start",
    "systemctl --user restart",
    "systemctl --user stop",
    "kill",
    "pkill",
    "killall",
    # --- Ubuntu 26.04: network / radio state ---
    "nmcli radio",
    "nmcli networking",
    "nmcli connection up",
    "nmcli connection down",
    "rfkill unblock",
    "rfkill block",
    "resolvectl flush-caches",
    # --- Ubuntu 26.04: desktop / peripheral state ---
    "gsettings set",
    "gdctl set",
    "wpctl set-default",
    "wpctl set-mute",
    "wpctl set-volume",
    "amixer -d pulse sset",
    "bluetoothctl power",
    "brightnessctl set",
    "modprobe",
    "cancel -a",
    # --- Ubuntu 26.04: packages, storage, time ---
    "apt update",
    "apt install",
    "apt clean",
    "apt-get update",
    "apt-get install",
    "apt-get --fix-broken",
    "dpkg --configure",
    "journalctl --vacuum-size",
    "journalctl --vacuum-time",
    "timedatectl set-ntp",
    "timedatectl set-timezone",
    "timedatectl set-time",
    "mount -o remount",
    "udisksctl mount",
    "udisksctl unmount",
]

# Red: hard blocked (never allowed)
RED_COMMANDS = [
    # --- Windows ---
    "remove-item -path c:\\windows",
    "remove-item -recurse c:\\windows",
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
    # --- Ubuntu 26.04: destructive filesystem operations ---
    "rm -rf /",
    "rm -fr /",
    "mkfs",
    "dd if=",
    "> /etc/passwd",
    "> /etc/shadow",
    "chmod 777 /",
    "chmod -r 777 /",
    # --- Ubuntu 26.04: privilege escalation and account tampering ---
    "usermod -ag sudo",
    "usermod -g sudo",
    "gpasswd -a",
    "adduser",
    "useradd",
    "passwd root",
    "visudo",
    "chpasswd",
    # --- Ubuntu 26.04: disabling security controls ---
    "ufw disable",
    "iptables -f",
    "nft flush ruleset",
    "setenforce 0",
    "aa-disable",
    "systemctl disable apparmor",
    "systemctl stop apparmor",
    "mokutil --disable-validation",
    # --- Ubuntu 26.04: bootloader and power state ---
    "grub-install",
    "update-grub",
    "reboot",
    "poweroff",
    "init 0",
    "init 6",
]


def _normalize(command: str) -> str:
    """Lowercase and collapse whitespace so 'net    user' matches 'net user'."""
    return re.sub(r"\s+", " ", command).lower().strip()


def _match_len(command: str, patterns: list[str]) -> int:
    """Length of the longest pattern in `patterns` present in `command`.

    Patterns match on token boundaries so short entries ('ls', 'kill') do not
    fire inside a longer word ('lsblk', 'killall' -> its own entry).
    Returns 0 when nothing matches.
    """
    best = 0
    for pattern in patterns:
        if len(pattern) <= best:
            continue
        regex = r"(?<![a-z0-9_-])" + re.escape(pattern) + r"(?![a-z0-9_-])"
        if re.search(regex, command):
            best = len(pattern)
    return best


def validate_command(command: str) -> SafetyTier:
    """Classify a command into a safety tier.

    Resolution rules:
      1. Red is absolute — any blocked pattern anywhere wins.
      2. Otherwise the **most specific** matching pattern decides, so
         'ipconfig /all' stays Green while 'ipconfig /flushdns' is Yellow, and
         'sudo apt-get check' stays Green under the blanket 'sudo' rule.
      3. Nothing matched: Green (read-only by assumption).
    """
    cmd = _normalize(command)

    if _match_len(cmd, RED_COMMANDS):
        return SafetyTier.RED

    yellow = _match_len(cmd, YELLOW_COMMANDS)
    green = _match_len(cmd, GREEN_COMMANDS)

    if yellow > green:
        return SafetyTier.YELLOW
    return SafetyTier.GREEN


def is_allowed(command: str) -> bool:
    return validate_command(command) != SafetyTier.RED
