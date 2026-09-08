import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge.runbook_matcher import match_runbook


def test_matches_print_spooler():
    result = match_runbook("My print job is stuck in the queue and I cannot delete it")
    assert result is not None
    assert result["runbook_id"] == "RB-PRINT-001"


def test_matches_vpn():
    result = match_runbook("VPN connected but cannot reach the intranet")
    assert result is not None
    assert result["runbook_id"] == "RB-VPN-001"


def test_no_match_for_unrelated():
    result = match_runbook("my keyboard is physically broken")
    assert result is None