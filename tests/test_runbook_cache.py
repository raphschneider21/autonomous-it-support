"""Runbook store caching.

`load_all_runbooks()` with no argument now resolves to the Ubuntu store, which
is the only platform this project targets. The flat `fixtures/runbooks/*.yaml`
layout survives as the store named "default" purely so a test can point
`RUNBOOKS_DIR` at a temporary directory — no runbooks ship there any more.
These tests therefore name the store they mean rather than relying on which one
happens to be active.
"""
import os
import tempfile
import time

from src.knowledge import runbook_parser as rp


def _isolated_store(tmp: str):
    """Point the flat 'default' store at `tmp` and start from a cold cache."""
    rp.RUNBOOKS_DIR = tmp
    rp.clear_cache()


def test_cache_reuses_same_objects_across_calls():
    original_dir = rp.RUNBOOKS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "a.yaml"), "w") as f:
                f.write("runbook_id: RB-A\ntitle: A\n")
            _isolated_store(tmp)

            first = rp.load_all_runbooks(rp.DEFAULT_STORE)
            second = rp.load_all_runbooks(rp.DEFAULT_STORE)

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

            rp.load_all_runbooks(rp.DEFAULT_STORE)

            # Change the file and bump its mtime
            time.sleep(0.01)
            with open(path, "w") as f:
                f.write("runbook_id: RB-B\ntitle: B\n")
            os.utime(path, (time.time() + 1, time.time() + 1))

            reloaded = rp.load_all_runbooks(rp.DEFAULT_STORE)
            assert reloaded[0]["runbook_id"] == "RB-B"
    finally:
        rp.RUNBOOKS_DIR = original_dir
        rp.clear_cache()


def test_cache_empty_dir_returns_empty():
    original_dir = rp.RUNBOOKS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            _isolated_store(tmp)
            assert rp.load_all_runbooks(rp.DEFAULT_STORE) == []
    finally:
        rp.RUNBOOKS_DIR = original_dir
        rp.clear_cache()


def test_default_call_resolves_to_the_ubuntu_store():
    """The engine must not need an environment variable to find its runbooks.

    Shipping with the flat store as the default meant a stock checkout served
    three Windows runbooks on a Linux endpoint.
    """
    rp.clear_cache()
    assert rp.active_store() == rp.UBUNTU_STORE
    runbooks = rp.load_all_runbooks()
    assert len(runbooks) == 30
    assert {r["target_os"] for r in runbooks} == {"ubuntu_26_04"}


def test_stores_are_cached_independently():
    """One store's cache must not evict or shadow another's."""
    original_dir = rp.RUNBOOKS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "legacy.yaml"), "w") as f:
                f.write("runbook_id: RB-LEGACY\ntitle: Legacy\ntarget_os: windows_11\n")
            _isolated_store(tmp)

            legacy = rp.load_all_runbooks(rp.DEFAULT_STORE)
            ubuntu = rp.load_all_runbooks(rp.UBUNTU_STORE)

            assert legacy is rp.load_all_runbooks(rp.DEFAULT_STORE)
            assert ubuntu is rp.load_all_runbooks(rp.UBUNTU_STORE)
            assert {r["runbook_id"] for r in legacy}.isdisjoint(
                {r["runbook_id"] for r in ubuntu}
            )
    finally:
        rp.RUNBOOKS_DIR = original_dir
        rp.clear_cache()


def test_a_flat_store_does_not_recurse_into_subdirectories():
    """Stores are sibling retrieval spaces, never nested ones."""
    original_dir = rp.RUNBOOKS_DIR
    try:
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "top.yaml"), "w") as f:
                f.write("runbook_id: RB-TOP\ntitle: Top\n")
            nested = os.path.join(tmp, "some-other-store")
            os.mkdir(nested)
            with open(os.path.join(nested, "deep.yaml"), "w") as f:
                f.write("runbook_id: RB-DEEP\ntitle: Deep\n")
            _isolated_store(tmp)

            ids = {r["runbook_id"] for r in rp.load_all_runbooks(rp.DEFAULT_STORE)}
            assert ids == {"RB-TOP"}
    finally:
        rp.RUNBOOKS_DIR = original_dir
        rp.clear_cache()
