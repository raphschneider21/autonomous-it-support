"""Cross-store runbook consistency (@Dev2).

Guards the two data drifts @Dev1 found in the Milestone-1 contract validation
pass (`docs/contract-validation.md` §1): a runbook that *declares* one target
OS while *containing* commands for another, and a runbook that mixes dialects
inside itself.

Both fields are informational — retrieval never reads `target_os` — which is
exactly why they drifted silently. They matter for the demo narrative and for
the day `RealExecutor` runs these commands against a real endpoint, so they
are asserted here rather than left to review.

Unlike `test_ubuntu_knowledge_base.py`, this runs over **every** store.
"""
import re

import pytest

from src.knowledge.runbook_parser import (
    DEFAULT_STORE,
    UBUNTU_STORE,
    load_all_runbooks,
)

STORES = [DEFAULT_STORE, UBUNTU_STORE]

TARGET_OS_DIALECT = {
    "windows_11": "windows",
    "windows_10": "windows",
    "ubuntu_26_04": "linux",
}

# Markers that only make sense on one platform.
WINDOWS_MARKERS = [
    (r"\b(Get|Set|New|Remove|Start|Stop|Restart|Test|Clear|Add|Invoke|Select)-[A-Za-z]+\b",
     "PowerShell cmdlet"),
    (r"\bipconfig\b", "ipconfig"),
    (r"\bnet use\b", "net use"),
    (r"\b[cw]script\b", "Windows Script Host"),
    (r"\$env:", "PowerShell environment variable"),
    (r"[A-Za-z]:\\\\|[A-Za-z]:\\", "Windows drive path"),
]

LINUX_MARKERS = [
    (r"\bsudo\b", "sudo"),
    (r"\bsystemctl\b", "systemctl"),
    (r"\b(apt|apt-get|dpkg)\b", "Debian package tooling"),
    (r"\b(nmcli|resolvectl|timedatectl|journalctl|rfkill|udisksctl|brightnessctl"
     r"|gdctl|bluetoothctl|wpctl|pactl|gsettings|lsblk|findmnt|modprobe|pkill|lpstat)\b",
     "Linux CLI tool"),
    (r"(?<![A-Za-z0-9])/(var|etc|dev|run|proc|usr)/", "Linux filesystem path"),
]


def _commands(rb) -> list[tuple[str, str]]:
    out = []
    for section in ("pre_checks", "remediation_steps", "verification", "rollback_plan"):
        for item in rb.get(section) or []:
            out.append((section, item.get("command", "")))
    return out


def _hits(command: str, markers) -> list[str]:
    return [label for pattern, label in markers if re.search(pattern, command)]


ALL_RUNBOOKS = [(store, rb) for store in STORES for rb in load_all_runbooks(store)]
IDS = [f"{store}:{rb['runbook_id']}" for store, rb in ALL_RUNBOOKS]


@pytest.mark.parametrize("store,rb", ALL_RUNBOOKS, ids=IDS)
def test_target_os_is_a_known_value(store, rb):
    assert rb.get("target_os") in TARGET_OS_DIALECT, \
        f"{rb['runbook_id']} declares unknown target_os {rb.get('target_os')!r}"


@pytest.mark.parametrize("store,rb", ALL_RUNBOOKS, ids=IDS)
def test_commands_match_the_declared_target_os(store, rb):
    """Drift #1: three fixtures declared `linux` while running PowerShell."""
    dialect = TARGET_OS_DIALECT[rb["target_os"]]
    foreign = LINUX_MARKERS if dialect == "windows" else WINDOWS_MARKERS

    for section, command in _commands(rb):
        hits = _hits(command, foreign)
        assert not hits, (
            f"{rb['runbook_id']} declares target_os={rb['target_os']} but its "
            f"{section} command uses {hits}: {command!r}"
        )


@pytest.mark.parametrize("store,rb", ALL_RUNBOOKS, ids=IDS)
def test_no_command_mixes_both_dialects(store, rb):
    """Drift #2: a PowerShell cmdlet operating on a Linux CUPS path."""
    for section, command in _commands(rb):
        win = _hits(command, WINDOWS_MARKERS)
        lin = _hits(command, LINUX_MARKERS)
        assert not (win and lin), (
            f"{rb['runbook_id']} {section} command mixes Windows {win} with "
            f"Linux {lin}: {command!r}"
        )


@pytest.mark.parametrize("store,rb", ALL_RUNBOOKS, ids=IDS)
def test_every_runbook_command_has_a_mock_fixture(store, rb):
    """A command with no fixture silently returns a no-op and fails verification."""
    from src.executors.mock_executor import MockExecutor

    executor = MockExecutor()
    for section, command in _commands(rb):
        output = executor.run(command)["stdout"]
        assert not output.startswith("[MOCK] No fixture for:"), \
            f"{rb['runbook_id']} {section}: no mock fixture for {command!r}"


def test_runbook_ids_are_unique_across_all_stores():
    """Stores are separate retrieval spaces, but `runbooks.id` is a shared PK."""
    ids = [rb["runbook_id"] for _, rb in ALL_RUNBOOKS]
    duplicates = {i for i in ids if ids.count(i) > 1}
    assert not duplicates, f"runbook_id collision across stores: {duplicates}"


# --- Store switching (Milestone 6 cutover) ---------------------------------

def test_switching_stores_replaces_the_database_view(tmp_path, monkeypatch):
    """After a store switch, GET /api/runbooks must not advertise the old store.

    The database persists across restarts, so seeding is additive by default:
    flipping RUNBOOK_STORE left the previous platform's runbooks on display
    while the engine matched only the new store.
    """
    import src.database as db
    from src.knowledge.runbook_parser import seed_runbooks_db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()

    assert seed_runbooks_db(DEFAULT_STORE) == 3
    assert {r["target_os"] for r in db.get_all_runbooks()} == {"windows_11"}

    assert seed_runbooks_db(UBUNTU_STORE) == 30
    seeded = db.get_all_runbooks()
    assert {r["target_os"] for r in seeded} == {"ubuntu_26_04"}
    assert len(seeded) == 30


def test_pruning_keeps_runbooks_still_cited_by_an_incident(tmp_path, monkeypatch):
    """An incident's runbook link is audit evidence and must survive a switch."""
    import src.database as db
    from src.knowledge.runbook_parser import seed_runbooks_db

    monkeypatch.setattr(db, "DB_PATH", str(tmp_path / "t.db"))
    db.init_db()

    seed_runbooks_db(DEFAULT_STORE)
    db.insert_incident("INC-HISTORY", "print job stuck")
    db.update_incident("INC-HISTORY", status="resolved", runbook_id="RB-PRINT-001")

    seed_runbooks_db(UBUNTU_STORE)

    remaining = {r["id"] for r in db.get_all_runbooks()}
    assert "RB-PRINT-001" in remaining, "resolved incident lost its runbook link"
    assert "RB-VPN-001" not in remaining, "unreferenced stale runbook was not pruned"
