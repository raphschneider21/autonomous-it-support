import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.knowledge.runbook_parser import load_all_runbooks, load_runbook


def test_loads_all_runbooks():
    runbooks = load_all_runbooks()
    assert len(runbooks) == 3


def test_runbook_has_required_fields():
    for rb in load_all_runbooks():
        assert "runbook_id" in rb
        assert "title" in rb
        assert "trigger_signatures" in rb
        assert "remediation_steps" in rb
        assert "verification" in rb