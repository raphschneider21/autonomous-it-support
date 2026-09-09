"""Diagnostic Agent — runs read-only probes and reasons about what they show.

Two halves with different characters:

`diagnose()` is deterministic. Every category maps to a fixed set of read-only
commands, each checked against the allowlist before it runs. Determinism here
is deliberate: probes run on every incident, and an audit trail is worth more
when the evidence-gathering step is reproducible.

`assess()` is where the model earns its place. Reading `journalctl` and `df -h`
and reasoning to a root cause nobody scripted is the one job in this system a
lookup table cannot do. Claude does it; the heuristic below is the declared
fallback when no key is configured.
"""
from ..executors.executor_interface import IExecutor
from ..models import SafetyTier
from ..safety.safety_validator import classify as classify_command
from . import llm

# Read-only probes per category. Every command here must classify GREEN —
# `test_diagnostic_probes.py` asserts it, so a probe cannot quietly become
# state-altering.
DIAGNOSTIC_COMMANDS = {
    "network": [
        "nmcli -t -f STATE general",
        "resolvectl status",
        "rfkill list",
        "ping -c 4 1.1.1.1",
    ],
    "disk": [
        "df -h /",
        "du -sh /var/log",
        "lsblk -o NAME,SIZE,FSTYPE,MOUNTPOINTS",
        "findmnt -no OPTIONS /",
    ],
    "audio": [
        "wpctl status",
        "systemctl --user is-active pipewire",
        "pactl info",
    ],
    "display": [
        "gdctl show",
        "brightnessctl info",
    ],
    "printing": [
        "systemctl is-active cups",
        "lpstat -o",
    ],
    "packages": [
        "sudo apt-get check",
        "sudo dpkg --audit",
        "apt-cache policy",
    ],
    "desktop": [
        "systemctl --user is-active org.gnome.Shell@wayland.service",
        "ps -eo pid,etimes,stat,comm --sort=-etimes",
    ],
    "time": [
        "timedatectl status",
        "timedatectl show -p NTPSynchronized --value",
    ],
    "input": [
        "libinput list-devices",
        "gsettings get org.gnome.desktop.input-sources sources",
    ],
}

DEFAULT_COMMANDS = ["uname -a", "df -h /", "free -h"]

_FAILURE_MARKERS = ("fail", "inactive", "dead", "error", "not found",
                    "unavailable", "no space", "read-only", "disconnected")


def diagnose(category: str, executor: IExecutor) -> list[dict]:
    commands = _get_diagnostic_commands(category)

    # Deduplicate identical commands so we never run the same probe twice.
    seen: set[str] = set()
    unique_commands = [c for c in commands if not (c in seen or seen.add(c))]

    results = []
    for cmd in unique_commands:
        decision = classify_command(cmd)
        if decision.tier is SafetyTier.GREEN:
            output = executor.run(cmd)
            results.append({
                "command": cmd,
                "safety_tier": decision.tier.value,
                "exit_code": output["exit_code"],
                "stdout": output["stdout"],
                "stderr": output["stderr"],
            })
        else:
            # A probe that is not read-only is a bug in this module, not a
            # decision for the runtime to make. Record it and move on.
            results.append({
                "command": cmd,
                "safety_tier": decision.tier.value,
                "exit_code": None,
                "stdout": "",
                "stderr": f"Probe skipped — not a read-only command: {decision.reason}",
            })
    return results


def _get_diagnostic_commands(category: str) -> list[str]:
    return DIAGNOSTIC_COMMANDS.get(category, DEFAULT_COMMANDS)


def assess(diagnostics: list[dict], category: str) -> dict:
    """Reason from probe output to a root cause. Claude first, heuristic after."""
    evidence = "\n\n".join(
        llm.wrap_evidence(d["command"], f"exit={d['exit_code']}\n{d['stdout']}\n{d['stderr']}")
        for d in (diagnostics or [])
    )

    if evidence:
        result = llm.call_agent(
            "DiagnosticAgent",
            f"Reported category: {category}\n\nDiagnostic output:\n{evidence}",
            expect_keys=("root_cause", "evidence"),
        )
        if result:
            result["agent"] = "DiagnosticAgent"
            result.setdefault("confidence", 0.5)
            return result

    return _assess_heuristic(diagnostics, category)


def _assess_heuristic(diagnostics: list[dict], category: str) -> dict:
    """Declared fallback: did any probe report something that looks wrong?"""
    failing = [
        d for d in (diagnostics or [])
        if d.get("exit_code") not in (0, None)
        or any(m in (d.get("stdout") or "").lower() for m in _FAILURE_MARKERS)
        or any(m in (d.get("stderr") or "").lower() for m in _FAILURE_MARKERS)
    ]

    if failing:
        return {
            "agent": "DiagnosticAgent",
            "root_cause": f"infrastructure/{category}",
            "evidence": (
                f"{len(failing)} of {len(diagnostics)} probes reported a fault: "
                + ", ".join(d["command"] for d in failing[:3])
            ),
            "confidence": 0.5,
            "proposed_command": None,
            "injection_observed": False,
            "_source": "heuristic-fallback",
        }

    return {
        "agent": "DiagnosticAgent",
        "root_cause": f"infrastructure/{category}",
        "evidence": "All read-only probes reported the endpoint responding normally.",
        "confidence": 0.3,
        "proposed_command": None,
        "injection_observed": False,
        "_source": "heuristic-fallback",
    }
