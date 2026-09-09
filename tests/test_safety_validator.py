"""Unit tests for the command allowlist.

Behavioural counterpart to `test_allowlist_adversarial.py`: that file proves
dangerous commands are refused, this one proves the classifier's *mechanics*
are right — tiering, sudo policy, arity, and the reasons it gives.

The previous version of this file tested a blocklist against Windows
PowerShell (`Get-Service`, `net user`, `ipconfig /flushdns`). Both the platform
and the mechanism are gone.
"""
import pytest

from src.models import SafetyTier
from src.safety.safety_validator import (
    classify,
    explain,
    is_allowed,
    split_command,
    validate_command,
)


# --- The default is denial ------------------------------------------------

def test_unknown_command_is_denied_not_allowed():
    """The single most important property: unknown means no."""
    decision = classify("some-tool --that-nobody-allowlisted")
    assert decision.tier is SafetyTier.RED
    assert not decision.allowed
    assert "not on the allowlist" in decision.reason


def test_empty_command_is_denied():
    for value in ("", "   ", "\t", None):
        assert validate_command(value) is SafetyTier.RED
        assert not is_allowed(value)


def test_denial_distinguishes_forbidden_from_unknown():
    """An escalation ticket reads differently for each, so the reasons differ."""
    assert "forbidden list" in explain("dd if=/dev/zero of=/dev/sda")
    assert "not on the allowlist" in explain("some-tool --flag")


# --- Tiering --------------------------------------------------------------

@pytest.mark.parametrize("command", [
    "systemctl is-active cups",
    "systemctl status nginx",
    "journalctl -u systemd-resolved -n 100",
    "df -h /",
    "du -sh /var/log",
    "free -h",
    "uname -a",
    "resolvectl query ubuntu.com",
    "timedatectl status",
    "nmcli -t -f STATE general",
    "wpctl status",
    "gsettings get org.gnome.desktop.peripherals.touchpad tap-to-click",
    "ping -c 4 1.1.1.1",
    "cat /etc/resolv.conf",
])
def test_read_only_commands_are_green(command):
    assert validate_command(command) is SafetyTier.GREEN


@pytest.mark.parametrize("command", [
    "sudo systemctl restart NetworkManager",
    "sudo systemctl restart systemd-resolved",
    "systemctl --user restart pipewire",
    "nmcli radio wifi off",
    "sudo resolvectl flush-caches",
    "sudo timedatectl set-ntp true",
    "sudo apt-get --fix-broken install -y",
    "sudo dpkg --configure -a",
    "sudo journalctl --vacuum-size=50M",
    "gsettings set org.gnome.desktop.peripherals.touchpad tap-to-click true",
    "wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.70",
    "sudo modprobe -r psmouse",
])
def test_state_altering_commands_are_yellow(command):
    assert validate_command(command) is SafetyTier.YELLOW


def test_green_and_yellow_both_execute_under_the_confirmed_model():
    """One up-front consent covers both tiers; only RED stops the agent."""
    assert is_allowed("systemctl is-active nginx")
    assert is_allowed("sudo systemctl restart nginx")
    assert not is_allowed("sudo systemctl restart apparmor")


# --- Sudo policy ----------------------------------------------------------

def test_sudo_required_rules_reject_the_unelevated_form():
    assert validate_command("sudo apt-get check") is SafetyTier.GREEN
    assert validate_command("apt-get check") is SafetyTier.RED


def test_sudo_forbidden_rules_reject_the_elevated_form():
    """A user-session command has no business running as root."""
    assert validate_command("systemctl --user restart pipewire") is SafetyTier.YELLOW
    assert validate_command("sudo systemctl --user restart pipewire") is SafetyTier.RED


def test_bare_and_flagged_sudo_are_denied():
    for command in ("sudo", "sudo -i", "sudo -u root systemctl status nginx"):
        assert validate_command(command) is SafetyTier.RED


# --- Arity: extra tokens are how payloads get smuggled --------------------

def test_extra_trailing_tokens_deny_the_command():
    assert is_allowed("uname -a")
    assert not is_allowed("uname -a /etc/shadow")


def test_missing_required_argument_denies_the_command():
    assert not is_allowed("systemctl is-active")
    assert not is_allowed("systemctl restart")


# --- Restricted vocabularies ----------------------------------------------

def test_restart_is_confined_to_managed_units():
    assert is_allowed("sudo systemctl restart cups")
    for unit in ("apparmor", "ufw", "sshd", "auditd"):
        assert not is_allowed(f"sudo systemctl restart {unit}"), unit


def test_status_is_readable_for_any_unit():
    """Reading state is harmless; changing it is not."""
    assert validate_command("systemctl status apparmor") is SafetyTier.GREEN
    assert validate_command("sudo systemctl stop apparmor") is SafetyTier.RED


def test_cat_is_confined_to_config_trees():
    assert is_allowed("cat /etc/resolv.conf")
    assert is_allowed("cat /etc/NetworkManager/conf.d/default-wifi-powersave-on.conf")
    assert not is_allowed("cat /etc/shadow")
    assert not is_allowed("cat /home/user/.ssh/id_rsa")


def test_path_arguments_are_normalised_before_the_root_check():
    assert not is_allowed("truncate -s 0 /var/log/../../dev/sda")
    assert is_allowed("truncate -s 0 /var/log/syslog")


def test_numeric_arguments_are_range_checked():
    assert is_allowed("ping -c 4 1.1.1.1")
    assert not is_allowed("ping -c 999999 1.1.1.1")
    assert is_allowed("wpctl set-volume @DEFAULT_AUDIO_SINK@ 0.70")
    assert not is_allowed("wpctl set-volume @DEFAULT_AUDIO_SINK@ 99")


# --- Tokenisation ---------------------------------------------------------

def test_whitespace_is_normalised():
    assert validate_command("  systemctl    is-active     cups  ") is SafetyTier.GREEN


def test_case_is_significant_because_linux_binaries_are():
    """Unlike the old Windows blocklist, casing is not folded: `RM` is not `rm`."""
    assert not is_allowed("SYSTEMCTL IS-ACTIVE CUPS")


def test_absolute_binary_paths_resolve_to_the_same_rule_check():
    assert not is_allowed("/bin/rm -rf /")


def test_unbalanced_quotes_are_denied_not_crashed():
    assert not is_allowed("gsettings set org.gnome.x key \"unterminated")


def test_split_command_produces_an_argument_list():
    assert split_command("sudo systemctl restart nginx") == [
        "sudo", "systemctl", "restart", "nginx",
    ]


# --- Placeholders ---------------------------------------------------------

def test_runbook_placeholders_validate_statically_only():
    templated = "sudo timedatectl set-timezone {timezone}"
    assert is_allowed(templated, allow_placeholders=True)
    assert not is_allowed(templated)
    assert is_allowed("sudo timedatectl set-timezone Europe/Zurich")
