import os
import tempfile
import time
from unittest.mock import patch

from src.knowledge import runbook_parser as rp


def test_cache_reuses_same_objects_across_calls():
    original_dir = rp.RUNBOOKS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        with open(os.path.join(tmp, "a.yaml"), "w") as f:
            f.write("runbook_id: RB-A\ntitle: A\n")
        rp.RUNBOOKS_DIR = tmp
        rp._cached_runbooks = None

        first = rp.load_all_runbooks()
        second = rp.load_all_runbooks()

        # Same cached list (identity), not a fresh parse
        assert first is second
        assert first[0]["runbook_id"] == "RB-A"

        rp.RUNBOOKS_DIR = original_dir
        rp._cached_runbooks = None


def test_cache_invalidates_when_file_changes():
    original_dir = rp.RUNBOOKS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        path = os.path.join(tmp, "a.yaml")
        with open(path, "w") as f:
            f.write("runbook_id: RB-A\ntitle: A\n")
        rp.RUNBOOKS_DIR = tmp
        rp._cached_runbooks = None

        rp.load_all_runbooks()

        # Change the file and bump its mtime
        time.sleep(0.01)
        with open(path, "w") as f:
            f.write("runbook_id: RB-B\ntitle: B\n")
        os.utime(path, (time.time() + 1, time.time() + 1))

        reloaded = rp.load_all_runbooks()
        assert reloaded[0]["runbook_id"] == "RB-B"

        rp.RUNBOOKS_DIR = original_dir
        rp._cached_runbooks = None


def test_cache_empty_dir_returns_empty():
    original_dir = rp.RUNBOOKS_DIR
    with tempfile.TemporaryDirectory() as tmp:
        rp.RUNBOOKS_DIR = tmp
        rp._cached_runbooks = None
        assert rp.load_all_runbooks() == []
        rp.RUNBOOKS_DIR = original_dir
        rp._cached_runbooks = None