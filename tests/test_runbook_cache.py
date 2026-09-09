import os
import tempfile
import time

from src.knowledge import runbook_parser as rp


def _isolated_store(tmp: str):
    """Point the default store at `tmp` and start from a cold cache."""
    rp.RUNBOOKS_DIR = tmp
    rp.clear_cache()


def test_cache_reuses_same_objects_across_calls():
    original_dir = rp.RUNBOOKS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.yaml"), "w") as f:
                f.write("runbook_id: RB-A\ntitle: A\n")
            _isolated_store(tmp)

            first = rp.load_all_runbooks()
            second = rp.load_all_runbooks()

            # Same cached list (identity), not a fresh parse
            assert first is second
            assert first[0]["runbook_id"] == "RB-A"
    finally:
        rp.RUNBOOKS_DIR = original_dir
        rp.clear_cache()


def test_cache_invalidates_when_file_changes():
    original_dir = rp.RUNBOOKS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "a.yaml")
            with open(path, "w") as f:
                f.write("runbook_id: RB-A\ntitle: A\n")
            _isolated_store(tmp)

            rp.load_all_runbooks()

            # Change the file and bump its mtime
            time.sleep(0.01)
            with open(path, "w") as f:
                f.write("runbook_id: RB-B\ntitle: B\n")
            os.utime(path, (time.time() + 1, time.time() + 1))

            reloaded = rp.load_all_runbooks()
            assert reloaded[0]["runbook_id"] == "RB-B"
    finally:
        rp.RUNBOOKS_DIR = original_dir
        rp.clear_cache()


def test_cache_empty_dir_returns_empty():
    original_dir = rp.RUNBOOKS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_store(tmp)
            assert rp.load_all_runbooks() == []
    finally:
        rp.RUNBOOKS_DIR = original_dir
        rp.clear_cache()


def test_stores_are_cached_independently():
    """The Ubuntu store must not evict or shadow the default store."""
    rp.clear_cache()
    default = rp.load_all_runbooks()
    ubuntu = rp.load_all_runbooks(rp.UBUNTU_STORE)

    assert default is rp.load_all_runbooks()
    assert ubuntu is rp.load_all_runbooks(rp.UBUNTU_STORE)
    assert {r["runbook_id"] for r in default}.isdisjoint({r["runbook_id"] for r in ubuntu})


def test_default_store_does_not_recurse_into_sub_stores():
    """Windows fixtures and the Ubuntu store stay in separate retrieval spaces."""
    rp.clear_cache()
    assert all(r["target_os"] != "ubuntu_26_04" for r in rp.load_all_runbooks())
