"""Invariants for the Ubuntu 26.04 runbook knowledge base (@Dev2).

These are the guarantees the rest of the system is allowed to rely on:
the store parses, the schema holds, nothing auto-executes a state change
without human approval, no command depends on a subsystem Ubuntu 26.04 has
removed, and every runbook can actually be driven end-to-end against the
mock VM endpoint used in the live demo.
"""
import json
import os
import re

import pytest

from src.executors.mock_executor import MockExecutor
from src.knowledge.runbook_parser import (
    UBUNTU_STORE,
    load_all_runbooks,
    load_runbook,
    store_dir,
)
from src.models import SafetyTier
from src.safety.safety_validator import validate_command

RUNBOOKS = load_all_runbooks(UBUNTU_STORE)
DATASET = os.path.join(os.path.dirname(__file__), "dataset_ubuntu_easy.json")

# Ubuntu 26.04 ships a Wayland-only GNOME session and a PipeWire-only audio
# stack. These binaries either no longer reach the session at all or only
# affect XWayland clients, so a runbook that uses one silently does nothing.
REMOVED_ON_2604 = ["xrandr", "setxkbmap", "xkill", "wmctrl", "pulseaudio -k", "gnome-shell --replace"]

READ_ONLY_VERB = re.compile(
    r"\b(show|status|list|list-timezones|get|query|info|audit|check|ping|ps|findmnt|lsblk|fuser|pgrep|lsmod)\b",
    re.IGNORECASE,
)


def test_store_is_not_empty():
    assert len(RUNBOOKS) == 30


def test_every_runbook_has_the_required_schema_fields():
    for rb in RUNBOOKS:
        assert rb["schema_version"] == "1.1", rb.get("runbook_id")
        assert rb["target_os"] == "ubuntu_26_04", rb["runbook_id"]
        assert rb["environment"] in {"vm-safe", "physical-only"}, rb["runbook_id"]
        for field in ("runbook_id", "title", "tags", "trigger_signatures",
                      "remediation_steps", "verification"):
            assert rb.get(field), f"{rb.get('runbook_id')} missing {field}"


def test_runbook_ids_are_unique_and_match_their_filename():
    ids = [rb["runbook_id"] for rb in RUNBOOKS]
    assert len(ids) == len(set(ids))
    for path in sorted(os.listdir(store_dir(UBUNTU_STORE))):
        rb = load_runbook(os.path.join(store_dir(UBUNTU_STORE), path))
        expected = rb["runbook_id"].lower().replace("rb-", "") + ".yaml"
        assert path == expected, f"{rb['runbook_id']} should live in {expected}"


def test_every_runbook_has_trigger_symptoms_and_at_least_one_step():
    for rb in RUNBOOKS:
        assert rb["trigger_signatures"]["symptoms"], rb["runbook_id"]
        # A runbook with zero remediation steps is invalid (docs/schema.md).
        assert rb["remediation_steps"], rb["runbook_id"]
        for step in rb["remediation_steps"]:
            assert step["command"].strip(), rb["runbook_id"]
            assert step["description"].strip(), rb["runbook_id"]


def test_parameter_placeholders_are_all_resolved():
    """No `{placeholder}` may survive into a command handed to an executor."""
    for rb in RUNBOOKS:
        declared = {p["name"] for p in rb.get("parameters", [])}
        for section in ("pre_checks", "remediation_steps", "verification", "rollback_plan"):
            for item in rb.get(section) or []:
                leftover = re.findall(r"\{([a-z_]+)\}", item["command"])
                assert not leftover, f"{rb['runbook_id']} unresolved {leftover} in {section}"
        for name in declared:
            assert name.islower(), rb["runbook_id"]


# --- Safety invariants -----------------------------------------------------

def test_no_runbook_command_is_blocked():
    """A shipped runbook must never contain a Red-tier command."""
    for rb in RUNBOOKS:
        for section in ("pre_checks", "remediation_steps", "verification", "rollback_plan"):
            for item in rb.get(section) or []:
                assert validate_command(item["command"]) != SafetyTier.RED, \
                    f"{rb['runbook_id']}: {item['command']}"


def test_state_altering_steps_require_human_approval():
    """Every remediation step is either Yellow (approval-gated) or read-only.

    This is the guarantee that makes the knowledge base safe to auto-run: a
    step that changes the endpoint cannot be classified Green and slip past
    the approval gate.
    """
    for rb in RUNBOOKS:
        for step in rb["remediation_steps"]:
            cmd = step["command"]
            tier = validate_command(cmd)
            if tier == SafetyTier.GREEN:
                assert READ_ONLY_VERB.search(cmd), \
                    f"{rb['runbook_id']}: '{cmd}' auto-executes but is not read-only"
            else:
                assert tier == SafetyTier.YELLOW, f"{rb['runbook_id']}: {cmd}"


def test_diagnostic_and_verification_commands_are_read_only():
    """Pre-checks and verification must never change the endpoint."""
    for rb in RUNBOOKS:
        for section in ("pre_checks", "verification"):
            for item in rb.get(section) or []:
                assert validate_command(item["command"]) == SafetyTier.GREEN, \
                    f"{rb['runbook_id']}: {section} step '{item['command']}' is not read-only"


def test_elevated_steps_are_never_auto_approved():
    for rb in RUNBOOKS:
        for step in rb["remediation_steps"]:
            if step.get("elevation_required") and not READ_ONLY_VERB.search(step["command"]):
                assert validate_command(step["command"]) == SafetyTier.YELLOW, \
                    f"{rb['runbook_id']}: {step['command']}"


# --- Ubuntu 26.04 platform correctness -------------------------------------

def test_no_command_uses_a_subsystem_removed_in_2604():
    for rb in RUNBOOKS:
        for section in ("pre_checks", "remediation_steps", "verification", "rollback_plan"):
            for item in rb.get(section) or []:
                for removed in REMOVED_ON_2604:
                    assert removed not in item["command"], \
                        f"{rb['runbook_id']} uses '{removed}', which does not work on Ubuntu 26.04"


# --- Demo readiness against the mock VM endpoint ---------------------------

@pytest.mark.parametrize("rb", RUNBOOKS, ids=[r["runbook_id"] for r in RUNBOOKS])
def test_verification_passes_against_the_mock_vm(rb):
    """Every runbook must verify green against the Ubuntu 26.04 VM fixtures.

    Without this, a runbook would run its remediation and then escalate
    anyway because verification found no fixture to match.
    """
    executor = MockExecutor()
    for check in rb["verification"]:
        output = executor.run(check["command"])["stdout"]
        assert not output.startswith("[MOCK] No fixture for:"), \
            f"{rb['runbook_id']}: no VM fixture for '{check['command']}'"
        assert re.search(check["expected_output_regex"], output, re.IGNORECASE), \
            f"{rb['runbook_id']}: '{check['command']}' -> {output!r} " \
            f"does not match /{check['expected_output_regex']}/"


@pytest.mark.parametrize("rb", RUNBOOKS, ids=[r["runbook_id"] for r in RUNBOOKS])
def test_pre_checks_have_vm_fixtures(rb):
    executor = MockExecutor()
    for check in rb.get("pre_checks") or []:
        output = executor.run(check["command"])["stdout"]
        assert re.search(check["expected_output_regex"], output, re.IGNORECASE), \
            f"{rb['runbook_id']}: pre-check '{check['command']}' -> {output!r}"


# --- Coverage of the team's training dataset -------------------------------

def test_every_resolvable_dataset_case_has_a_runbook():
    with open(DATASET) as f:
        cases = json.load(f)["test_cases"]

    resolvable = {c["id"] for c in cases if c["expected"] == "resolve"}
    covered = {rb["source_case"] for rb in RUNBOOKS}
    assert resolvable - covered == set(), f"uncovered cases: {sorted(resolvable - covered)}"


def test_escalation_cases_deliberately_have_no_runbook():
    """UB-031..033 are beyond a Tier-1 fix; a runbook for them would be wrong."""
    with open(DATASET) as f:
        cases = json.load(f)["test_cases"]

    escalate = {c["id"] for c in cases if c["expected"] == "escalate"}
    covered = {rb["source_case"] for rb in RUNBOOKS}
    assert escalate & covered == set()
