"""Default-deny command allowlist.

A blocklist cannot work here. Once a language model proposes the commands, the
space of dangerous strings is unbounded — and with one up-front consent and no
per-action approval gate, this module is the only control between the model and
the machine. So the default is *deny*: a command runs only if it matches an
explicit rule, argument by argument. Anything unrecognised escalates.

Three outcomes:

    GREEN   read-only diagnostics, auto-executed
    YELLOW  state-altering but reversible and local, auto-executed inside the
            user's consent window
    RED     denied. Either explicitly forbidden (a known-dangerous shape we
            recognise and refuse by name) or simply not on the allowlist.
            Both escalate to Tier 2; neither ever runs.

Matching happens on `shlex`-split tokens with exact arity, so shell chaining
cannot smuggle a payload past a benign prefix: `df -h; cat /etc/shadow` splits
into four tokens, the `df` rule accepts at most two, and the command is denied.
`RealExecutor` also runs argument lists rather than `shell=True`, so
metacharacters are inert even if one reaches it — see `split_command`.

Adding a rule is a security change. The adversarial suite in
`tests/test_allowlist_adversarial.py` must stay green, and a widened rule needs
a matching test in the same commit.
"""
import os
import re
import shlex
from dataclasses import dataclass, field
from typing import Callable, Optional, Sequence, Union

from ..models import SafetyTier


# --------------------------------------------------------------------------
# Argument matchers
# --------------------------------------------------------------------------

class Matcher:
    """Validates a single argument token."""

    name = "arg"

    def match(self, token: str) -> bool:  # pragma: no cover - interface
        raise NotImplementedError

    def __repr__(self) -> str:
        return f"<{self.name}>"


class Re(Matcher):
    """Token must match a regex in full."""

    def __init__(self, pattern: str, name: str = "arg"):
        self._re = re.compile(pattern)
        self.name = name

    def match(self, token: str) -> bool:
        return bool(self._re.fullmatch(token))


class OneOf(Matcher):
    """Token must be one of a fixed set."""

    def __init__(self, *values: str, name: str = "choice"):
        self.values = frozenset(values)
        self.name = name

    def match(self, token: str) -> bool:
        return token in self.values


class PathUnder(Matcher):
    """Token must be an absolute path inside one of `roots`.

    Normalised before comparison so `/var/log/../../etc/shadow` cannot pass as
    a path under /var/log.
    """

    def __init__(self, *roots: str, name: str = "path"):
        self.roots = tuple(os.path.normpath(r).rstrip("/") + "/" for r in roots)
        self.name = name

    def match(self, token: str) -> bool:
        if not token.startswith("/"):
            return False
        norm = os.path.normpath(token)
        return any(norm.startswith(r) or norm == r.rstrip("/") for r in self.roots)


class IntRange(Matcher):
    def __init__(self, lo: int, hi: int, name: str = "int"):
        self.lo, self.hi, self.name = lo, hi, name

    def match(self, token: str) -> bool:
        try:
            return self.lo <= int(token) <= self.hi
        except ValueError:
            return False


class FloatRange(Matcher):
    def __init__(self, lo: float, hi: float, name: str = "float"):
        self.lo, self.hi, self.name = lo, hi, name

    def match(self, token: str) -> bool:
        try:
            return self.lo <= float(token.rstrip("%")) <= self.hi
        except ValueError:
            return False


class Rest(Matcher):
    """Absorbs zero or more trailing tokens, each validated by `inner`."""

    def __init__(self, inner: Matcher, name: str = "rest"):
        self.inner = inner
        self.name = name

    def match(self, token: str) -> bool:
        return self.inner.match(token)


class Opt(Matcher):
    """A single optional token."""

    def __init__(self, inner: Matcher, name: str = "opt"):
        self.inner = inner
        self.name = name

    def match(self, token: str) -> bool:
        return self.inner.match(token)


# --------------------------------------------------------------------------
# Concrete argument vocabularies
# --------------------------------------------------------------------------

# A systemd unit name. Deliberately excludes every shell metacharacter.
UNIT = Re(r"[A-Za-z0-9@:._\\-]{1,64}(\.(service|socket|target|timer|mount|path))?", "unit")

# Units the agent may restart/start/stop. Restricting this set is the point:
# `systemctl stop apparmor` must not be reachable through a generic rule.
MANAGED_UNITS = OneOf(
    "NetworkManager", "NetworkManager.service",
    "bluetooth", "bluetooth.service",
    "cups", "cups.service",
    "gdm", "gdm.service",
    "systemd-resolved", "systemd-resolved.service",
    "systemd-timesyncd", "systemd-timesyncd.service",
    "unattended-upgrades", "unattended-upgrades.service",
    "nginx", "nginx.service",
    "cron", "cron.service",
    name="managed-unit",
)

# User-session units (systemctl --user).
USER_UNITS = OneOf(
    "org.gnome.Shell@wayland.service", "org.gnome.Shell@x11.service",
    "pipewire", "pipewire.service",
    "pipewire-pulse", "pipewire-pulse.service",
    "wireplumber", "wireplumber.service",
    "gnome-session-restart-dbus.service",
    name="user-unit",
)

# A package name. No slashes, no metacharacters.
PKG = Re(r"[a-z0-9][a-z0-9+._-]{0,64}", "package")

# A process name for pgrep/pkill. This is a substituted runbook placeholder
# ({app_name}), so it is an injection surface: 'firefox; rm -rf /' must fail.
PROC = Re(r"[A-Za-z0-9][A-Za-z0-9._-]{0,64}", "process")

# Kernel module name.
MODULE = Re(r"[a-z0-9_-]{1,64}", "module")

# Hostname or IP for ping/resolvectl. No metacharacters, no shell expansion.
HOST = Re(r"[A-Za-z0-9]([A-Za-z0-9.-]{0,253}[A-Za-z0-9])?", "host")

# IANA timezone.
TIMEZONE = Re(r"[A-Za-z][A-Za-z_+-]{0,30}(/[A-Za-z0-9][A-Za-z0-9_+-]{0,30}){0,2}", "timezone")

# A dconf/gsettings schema and key.
SCHEMA = Re(r"[a-z][a-z0-9.-]{2,80}", "schema")
GKEY = Re(r"[a-z][a-z0-9-]{0,60}", "gsettings-key")
# A gsettings value. Permits the quoted list syntax the keyboard runbook needs
# while excluding every character that means something to a shell.
GVALUE = Re(r"[A-Za-z0-9 ,.'\[\](){}_@:/-]{1,120}", "gsettings-value")

# PipeWire node references and volumes.
SINK = Re(r"(@DEFAULT_AUDIO_(SINK|SOURCE)@|[0-9]{1,6})", "audio-node")
VOLUME = FloatRange(0.0, 1.5, "volume")
MUTE = OneOf("0", "1", "toggle", name="mute-state")

# Block device for udisksctl. Confined to /dev, and no partition-table devices.
BLOCKDEV = Re(r"/dev/(sd[a-z][0-9]{1,2}|nvme[0-9]n[0-9]p[0-9]{1,2}|mmcblk[0-9]p[0-9]{1,2})", "block-device")

# journalctl vacuum sizes/times.
VACUUM_SIZE = Re(r"--vacuum-size=[0-9]{1,6}[KMG]", "vacuum-size")
VACUUM_TIME = Re(r"--vacuum-time=[0-9]{1,4}(s|m|h|d|weeks|months)", "vacuum-time")

# `ps -eo` format strings and sort keys.
PS_FORMAT = Re(r"[a-z]+(,[a-z%]+){0,8}", "ps-format")
PS_SORT = Re(r"--sort=-?[a-z]+", "ps-sort")

# lsblk / findmnt column lists.
COLUMNS = Re(r"[A-Z]+(,[A-Z]+){0,8}", "columns")

# nmcli -t -f field lists and objects.
NM_FIELDS = Re(r"[A-Z0-9]+(,[A-Z0-9.-]+){0,8}", "nm-fields")

# A `sed -i` substitution. No flags are permitted after the closing delimiter,
# which excludes GNU sed's `e` (execute) and `w` (write-to-file) flags.
SED_SUBST = Re(r"s/[A-Za-z0-9 ._=-]{1,80}/[A-Za-z0-9 ._=-]{1,80}/", "sed-substitution")

# gdctl display-configuration tokens.
GDCTL_TOKEN = Re(r"(--[a-z-]{2,20}|[A-Za-z0-9@.:_-]{1,40})", "gdctl-token")

# Free-form but metacharacter-free token, for read-only flag positions.
FLAG = Re(r"-{1,2}[A-Za-z0-9][A-Za-z0-9=,.-]{0,40}", "flag")

# Paths the agent may `cat`. Arbitrary `cat` is not allowlisted: it would read
# /etc/shadow.
READABLE_CONF = PathUnder("/etc/NetworkManager", "/etc/systemd", name="config-path")

# Subtrees the agent may size or inspect for lock holders. `/etc` is
# deliberately absent: nothing in the runbook corpus needs it, and including it
# made `du -sh /etc/shadow` a legal command (caught by the adversarial suite).
INSPECTABLE_PATH = PathUnder("/var", "/home", "/tmp", name="inspect-path")


class _MountPoint(Matcher):
    """A filesystem mount point.

    Deliberately not `PathUnder("/")`: that would make every path on the system
    a legal argument, which is exactly the hole this module exists to close.
    """

    name = "mountpoint"
    _FIXED = frozenset({"/", "/home", "/var", "/boot", "/boot/efi", "/tmp", "/srv"})
    _ROOTS = ("/mnt/", "/media/", "/run/media/")

    def match(self, token: str) -> bool:
        if not token.startswith("/"):
            return False
        norm = os.path.normpath(token)
        return norm in self._FIXED or any(norm.startswith(r) for r in self._ROOTS)


MOUNTPOINT = _MountPoint()


# --------------------------------------------------------------------------
# Rule table
# --------------------------------------------------------------------------

Token = Union[str, Matcher]


@dataclass(frozen=True)
class Rule:
    tier: SafetyTier
    tokens: Sequence[Token]
    sudo: str = "optional"   # "required" | "optional" | "forbidden"
    note: str = ""

    def label(self) -> str:
        return " ".join(t if isinstance(t, str) else repr(t) for t in self.tokens)


def _G(*tokens: Token, sudo: str = "optional", note: str = "") -> Rule:
    return Rule(SafetyTier.GREEN, tokens, sudo, note)


def _Y(*tokens: Token, sudo: str = "optional", note: str = "") -> Rule:
    return Rule(SafetyTier.YELLOW, tokens, sudo, note)


RULES: list[Rule] = [
    # ---------- GREEN: read-only service and system state ----------
    _G("systemctl", "status", Opt(UNIT)),
    _G("systemctl", "is-active", UNIT),
    _G("systemctl", "is-enabled", UNIT),
    _G("systemctl", "list-units", Rest(FLAG)),
    _G("systemctl", "--user", "is-active", USER_UNITS),
    _G("systemctl", "--user", "status", Opt(USER_UNITS)),
    _G("journalctl", Rest(Re(r"(-u|-n|-p|-b|--since|--until|--no-pager|--user-unit|[A-Za-z0-9@._:-]{1,64}|[0-9]{1,4}|[a-z]+)", "journal-arg"))),
    _G("ps", "aux"),
    _G("ps", "-eo", PS_FORMAT, Opt(PS_SORT)),
    _G("pgrep", "-f", PROC),
    _G("pgrep", PROC),
    _G("lsmod"),
    _G("lsblk", Opt(OneOf("-o", "-f", "-a", name="lsblk-flag")), Opt(COLUMNS)),
    _G("findmnt", Rest(Re(r"(-no|-n|-o|OPTIONS|SOURCE|TARGET|FSTYPE|/[A-Za-z0-9/._-]{0,80})", "findmnt-arg"))),
    _G("df", Opt(OneOf("-h", "-H", "-i", name="df-flag")), Opt(MOUNTPOINT)),
    _G("df", OneOf("-h", "-H", "-i", name="df-flag"), INSPECTABLE_PATH),
    _G("du", OneOf("-sh", "-s", "-h", name="du-flag"), INSPECTABLE_PATH),
    _G("free", Opt(OneOf("-h", "-m", "-g", name="free-flag"))),
    _G("uname", Opt(FLAG)),
    _G("uptime"),
    _G("cat", READABLE_CONF, note="only NetworkManager/systemd config, never /etc/shadow"),
    _G("cat", "/etc/resolv.conf"),

    # ---------- GREEN: read-only subsystem queries ----------
    _G("resolvectl", "status", Opt(Re(r"[a-z0-9]{1,20}", "iface"))),
    _G("resolvectl", "query", HOST),
    _G("timedatectl", "status"),
    _G("timedatectl", "show", "-p", Re(r"[A-Za-z]{1,40}", "property"), Opt(OneOf("--value", name="value-flag"))),
    _G("timedatectl", "list-timezones"),
    _G("rfkill", "list", Opt(Re(r"[a-z]{1,20}", "rfkill-type"))),
    _G("nmcli", "-t", "-f", NM_FIELDS, Re(r"[a-z]{1,20}", "nm-object")),
    _G("nmcli", "general", "status"),
    _G("nmcli", "device", "status"),
    _G("nmcli", "connection", "show"),
    _G("bluetoothctl", "show"),
    _G("wpctl", "status"),
    _G("wpctl", "get-volume", SINK),
    _G("pactl", "info"),
    _G("pactl", "list", Rest(Re(r"(short|sinks|sources|modules|clients)", "pactl-arg"))),
    _G("amixer", "-d", "pulse", "sget", Re(r"[A-Za-z]{1,20}", "mixer-control")),
    _G("gsettings", "get", SCHEMA, GKEY),
    _G("gdctl", "show", Opt(OneOf("--verbose", name="verbose"))),
    _G("brightnessctl", "info"),
    _G("libinput", "list-devices"),
    _G("xinput", "list"),
    _G("lpstat", Rest(FLAG)),
    _G("apt-cache", "policy", Rest(PKG)),
    _G("apt", "list", "--upgradable"),
    _G("busctl", "--user", "call", "org.gnome.Shell", "/org/gnome/Shell",
       "org.freedesktop.DBus.Peer", "Ping"),
    _G("ping", "-c", IntRange(1, 10), HOST),
    _G("ping", HOST),

    # Read-only checks that need root to open their state files.
    _G("apt-get", "check", sudo="required"),
    _G("dpkg", "--audit", sudo="required"),
    _G("fuser", Opt(OneOf("-v", name="verbose")), INSPECTABLE_PATH, sudo="required"),

    # ---------- YELLOW: service lifecycle ----------
    _Y("systemctl", OneOf("restart", "start", "stop", "reload", name="verb"), MANAGED_UNITS,
       sudo="required", note="restricted unit set — apparmor/ufw are not reachable"),
    _Y("systemctl", "--user", OneOf("restart", "start", "stop", name="verb"),
       Rest(USER_UNITS), sudo="forbidden"),

    # ---------- YELLOW: network and radio state ----------
    _Y("nmcli", "radio", OneOf("wifi", "wwan", "all", name="radio"), OneOf("on", "off", name="state")),
    _Y("nmcli", "networking", OneOf("on", "off", name="state")),
    _Y("nmcli", "connection", OneOf("up", "down", name="verb"), Re(r"[A-Za-z0-9 ._-]{1,64}", "connection")),
    _Y("rfkill", OneOf("unblock", "block", name="verb"), Re(r"[a-z0-9]{1,20}", "rfkill-id"), sudo="optional"),
    _Y("resolvectl", "flush-caches", sudo="optional"),

    # ---------- YELLOW: desktop and peripherals ----------
    _Y("gsettings", "set", SCHEMA, GKEY, GVALUE, sudo="forbidden"),
    _Y("gdctl", "set", Rest(GDCTL_TOKEN), sudo="forbidden"),
    _Y("wpctl", "set-default", Re(r"[0-9]{1,6}", "node-id"), sudo="forbidden"),
    _Y("wpctl", "set-mute", SINK, MUTE, sudo="forbidden"),
    _Y("wpctl", "set-volume", SINK, VOLUME, sudo="forbidden"),
    _Y("amixer", "-d", "pulse", "sset", Re(r"[A-Za-z]{1,20}", "mixer-control"),
       Re(r"[0-9]{1,3}%?|unmute|mute", "mixer-value"), sudo="forbidden"),
    _Y("bluetoothctl", "power", OneOf("on", "off", name="state"), sudo="forbidden"),
    _Y("brightnessctl", "set", Re(r"[0-9]{1,3}%?|[+-][0-9]{1,3}%?", "brightness"), sudo="optional"),
    _Y("modprobe", Opt(OneOf("-r", name="remove")), MODULE, sudo="required"),
    _Y("cancel", "-a", sudo="optional"),
    _Y("pkill", OneOf("-TERM", "-KILL", "-HUP", name="signal"), "-f", PROC, sudo="forbidden"),
    _Y("killall", "-q", Rest(PKG), sudo="required"),

    # ---------- YELLOW: packages, storage, time ----------
    _Y("apt", OneOf("update", "clean", "autoclean", name="verb"), sudo="required"),
    _Y("apt-get", "update", sudo="required"),
    _Y("apt-get", "--fix-broken", "install", Opt(OneOf("-y", name="yes")), sudo="required"),
    _Y("dpkg", "--configure", "-a", sudo="required"),
    _Y("journalctl", VACUUM_SIZE, sudo="required"),
    _Y("journalctl", VACUUM_TIME, sudo="required"),
    _Y("timedatectl", "set-ntp", OneOf("true", "false", name="bool"), sudo="required"),
    _Y("timedatectl", "set-timezone", TIMEZONE, sudo="required"),
    _Y("mount", "-o", Re(r"remount(,[a-z]{1,10}){0,3}", "mount-opts"), MOUNTPOINT, sudo="required"),
    _Y("udisksctl", OneOf("mount", "unmount", name="verb"), "-b", BLOCKDEV, sudo="forbidden"),
    _Y("truncate", "-s", "0", PathUnder("/var/log", name="log-path"), sudo="optional",
       note="log files only — never a device node"),
    _Y("sed", "-i", SED_SUBST, PathUnder("/etc/NetworkManager", name="nm-config"), sudo="required",
       note="substitution only, no sed flags, one config tree"),
]


# --------------------------------------------------------------------------
# Explicitly forbidden shapes
# --------------------------------------------------------------------------
# These would be denied anyway by default-deny. They are named so the agent can
# report "recognised and refused" rather than "unrecognised", which is both a
# better audit record and a better demo.

FORBIDDEN_BINARIES = {
    "mkfs", "mkfs.ext4", "mkfs.xfs", "mkfs.btrfs", "fdisk", "sfdisk", "parted",
    "dd", "shred", "wipefs", "blkdiscard",
    "useradd", "adduser", "usermod", "userdel", "gpasswd", "chpasswd", "passwd", "visudo",
    "su", "sudoedit",
    "iptables", "ip6tables", "nft", "ufw", "setenforce", "aa-disable", "aa-teardown",
    "mokutil", "grub-install", "update-grub", "efibootmgr",
    "shutdown", "reboot", "poweroff", "halt", "init", "telinit",
    "nc", "ncat", "netcat", "socat", "telnet",
    "curl", "wget",
    "chmod", "chown", "chgrp", "setfacl",
    "rm", "rmdir", "mv", "unlink",
    "bash", "sh", "zsh", "dash", "python", "python3", "perl", "ruby", "eval", "exec",
    "crontab", "at", "systemd-run",
    "mail", "sendmail", "ssh", "scp", "rsync", "ftp",
}

# Characters that only ever mean shell interpretation. Their presence anywhere
# in the raw command is a denial: no allowlisted command needs them, and
# RealExecutor no longer runs a shell, so their presence signals an attempt.
_SHELL_METACHARS = re.compile(r"[;&|`$><\n\r\\]|\$\(|\(\)")


# --------------------------------------------------------------------------
# Decision
# --------------------------------------------------------------------------

@dataclass(frozen=True)
class Decision:
    tier: SafetyTier
    allowed: bool
    reason: str
    rule: Optional[str] = None
    tokens: tuple = field(default_factory=tuple)

    @property
    def requires_escalation(self) -> bool:
        return not self.allowed


def split_command(command: str) -> list[str]:
    """Token list suitable for `subprocess.run(..., shell=False)`.

    Raises ValueError on unbalanced quotes.
    """
    return shlex.split(command)


# A runbook step written as `pkill -TERM -f {app_name}` is validated twice: once
# statically against the YAML, where `{app_name}` is still a placeholder, and
# again at runtime once a value has been substituted in. Only the static pass
# accepts the placeholder form — otherwise `{app_name}` = "firefox; rm -rf /"
# would be waved through by the same rule that was meant to constrain it.
_PLACEHOLDER = re.compile(r"\{[a-z_][a-z0-9_]{0,30}\}")


def _token_ok(spec: Token, token: str, allow_placeholders: bool) -> bool:
    if allow_placeholders and _PLACEHOLDER.fullmatch(token):
        return not isinstance(spec, str)
    return (token == spec) if isinstance(spec, str) else spec.match(token)


def _match_rule(rule: Rule, tokens: list[str], had_sudo: bool,
                allow_placeholders: bool = False) -> bool:
    if rule.sudo == "required" and not had_sudo:
        return False
    if rule.sudo == "forbidden" and had_sudo:
        return False

    i = 0
    for spec in rule.tokens:
        if isinstance(spec, Rest):
            while i < len(tokens) and _token_ok(spec, tokens[i], allow_placeholders):
                i += 1
            continue
        if isinstance(spec, Opt):
            if i < len(tokens) and _token_ok(spec, tokens[i], allow_placeholders):
                i += 1
            continue
        if i >= len(tokens):
            return False
        if not _token_ok(spec, tokens[i], allow_placeholders):
            return False
        i += 1

    # Exact arity: leftover tokens mean this is not the command we allowed.
    return i == len(tokens)


def classify(command: str, allow_placeholders: bool = False) -> Decision:
    """Classify a command against the allowlist. Default is denial.

    `allow_placeholders` is for validating runbook YAML before substitution and
    must never be set on the runtime path.
    """
    if command is None or not command.strip():
        return Decision(SafetyTier.RED, False, "Empty command.")

    raw = command.strip()

    if _SHELL_METACHARS.search(raw):
        return Decision(
            SafetyTier.RED, False,
            "DENIED: shell metacharacters are not permitted in agent commands.",
        )

    try:
        tokens = split_command(raw)
    except ValueError as exc:
        return Decision(SafetyTier.RED, False, f"DENIED: unparseable command ({exc}).")

    if not tokens:
        return Decision(SafetyTier.RED, False, "Empty command.")

    had_sudo = False
    if tokens[0] == "sudo":
        had_sudo = True
        tokens = tokens[1:]
        # `sudo -u x`, `sudo su`, `sudo -i` etc. are never allowlisted.
        if not tokens or tokens[0].startswith("-"):
            return Decision(SafetyTier.RED, False, "DENIED: bare or flagged sudo invocation.")

    binary = os.path.basename(tokens[0])
    if binary in FORBIDDEN_BINARIES:
        return Decision(
            SafetyTier.RED, False,
            f"DENIED: '{binary}' is on the forbidden list "
            f"(destructive, privilege-altering, or capable of arbitrary execution).",
        )

    for rule in RULES:
        if _match_rule(rule, tokens, had_sudo, allow_placeholders):
            return Decision(
                rule.tier, True,
                "Read-only diagnostic. Safe to execute."
                if rule.tier is SafetyTier.GREEN
                else "State-altering but reversible and local. Runs inside the user's consent window.",
                rule.label(), tuple(tokens),
            )

    return Decision(
        SafetyTier.RED, False,
        f"DENIED: '{binary}' with these arguments is not on the allowlist. "
        f"Unknown commands escalate to Tier 2 rather than executing.",
        None, tuple(tokens),
    )


# --------------------------------------------------------------------------
# Compatibility surface
# --------------------------------------------------------------------------

def validate_command(command: str, allow_placeholders: bool = False) -> SafetyTier:
    """Tier for a command. RED means denied — forbidden or simply unknown."""
    return classify(command, allow_placeholders).tier


def is_allowed(command: str, allow_placeholders: bool = False) -> bool:
    return classify(command, allow_placeholders).allowed


def explain(command: str, allow_placeholders: bool = False) -> str:
    return classify(command, allow_placeholders).reason
