import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge.runbook_matcher import match_runbook


def test_matches_stuck_print_queue():
    result = match_runbook("My print job is stuck in the queue and I cannot delete it")
    assert result is not None
    assert result["runbook_id"] == "RB-CUPS-001"


def test_matches_wifi_drop():
    result = match_runbook("my wifi keeps dropping every few minutes")
    assert result is not None
    assert result["runbook_id"] == "RB-WIFI-001"


def test_no_match_for_unrelated():
    result = match_runbook("my keyboard is physically broken")
    assert result is None