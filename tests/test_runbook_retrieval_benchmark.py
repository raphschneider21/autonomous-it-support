"""Retrieval benchmark for the Ubuntu 26.04 knowledge base (@Dev2).

Measures runbook retrieval on two sets and records the metrics for the TDD
efficiency and experimentation sections:

  * `dataset_ubuntu_easy.json`  — the team's 33 training prompts, verbatim.
  * `dataset_ubuntu_paraphrases.json` — 36 held-out paraphrases plus three
    out-of-scope prompts, written so they do **not** reuse the wording stored
    in the runbooks' trigger signatures.

The verbatim set alone would flatter the matcher, because the dataset prompt
of each case was curated into the runbook it should retrieve. The paraphrase
set is the number that means something.

Errors are split by consequence, which matters more than raw accuracy:
  * `wrong`  — retrieved the WRONG runbook. Unsafe: the agent would run the
               wrong remediation on someone's machine. Must stay at zero.
  * `missed` — retrieved nothing when a runbook existed. Safe: the incident
               escalates to a human, which is the designed fallback.
"""
import json
import os
import time

import pytest

from src.knowledge.runbook_matcher import match_runbook
from src.knowledge.runbook_parser import UBUNTU_STORE, load_all_runbooks

HERE = os.path.dirname(__file__)
BENCHMARK_DIR = os.path.join(os.path.dirname(HERE), "data", "benchmarks")
STORE = UBUNTU_STORE


def _legacy_match(user_prompt: str, runbooks: list[dict]):
    """The word-overlap matcher this benchmark replaced, kept for comparison.

    Reproduces `match_runbook` as it stood before the Ubuntu store existed:
    raw word counts, +3 per tag substring, +10 per error code, accept at >= 3.
    It is only ever called from this benchmark.
    """
    best, best_score = None, 0
    prompt_lower = user_prompt.lower()
    for rb in runbooks:
        score = 0
        triggers = rb.get("trigger_signatures", {})
        for symptom in triggers.get("symptoms", []):
            score += sum(1 for w in symptom.lower().split() if w in prompt_lower)
        for tag in rb.get("tags", []):
            if tag.lower() in prompt_lower:
                score += 3
        if score > best_score:
            best, best_score = rb, score
    return best if best_score >= 3 else None


def _load_cases():
    with open(os.path.join(HERE, "dataset_ubuntu_easy.json")) as f:
        dataset = json.load(f)["test_cases"]
    with open(os.path.join(HERE, "dataset_ubuntu_paraphrases.json")) as f:
        paraphrases = json.load(f)["cases"]

    by_source = {rb["source_case"]: rb["runbook_id"] for rb in load_all_runbooks(STORE)}

    verbatim = [
        {"id": c["id"], "prompt": c["prompt"],
         "expected": by_source.get(c["id"]) if c["expected"] == "resolve" else None}
        for c in dataset
    ]
    held_out = [
        {"id": c["source_case"], "prompt": c["prompt"], "expected": c["expected_runbook"]}
        for c in paraphrases
    ]
    return verbatim, held_out


def _score_set(cases, matcher) -> dict:
    correct = correct_escalation = missed = wrong = 0
    latencies = []
    failures = []

    for case in cases:
        start = time.perf_counter()
        result = matcher(case["prompt"])
        latencies.append((time.perf_counter() - start) * 1000)

        got = result.get("runbook_id") if result else None
        expected = case["expected"]

        if expected is None and got is None:
            correct_escalation += 1
        elif got == expected:
            correct += 1
        elif got is None:
            missed += 1
            failures.append({"case": case["id"], "expected": expected, "got": None,
                             "consequence": "safe: escalated to a human"})
        else:
            wrong += 1
            failures.append({"case": case["id"], "expected": expected, "got": got,
                             "consequence": "unsafe: wrong remediation"})

    latencies.sort()
    total = len(cases)
    return {
        "cases": total,
        "correct": correct,
        "correct_escalation": correct_escalation,
        "missed_safe": missed,
        "wrong_unsafe": wrong,
        "accuracy": round((correct + correct_escalation) / total, 4) if total else 0.0,
        "latency_ms_mean": round(sum(latencies) / len(latencies), 4) if latencies else 0.0,
        "latency_ms_p95": round(latencies[int(len(latencies) * 0.95) - 1], 4) if latencies else 0.0,
        "failures": failures,
    }


def run_retrieval_benchmark(write: bool = False) -> dict:
    """Run both evaluation sets against the current and the legacy matcher.

    `write=False` (what pytest uses) returns the report without touching the
    recorded benchmark artifact.
    """
    verbatim, held_out = _load_cases()
    runbooks = load_all_runbooks(STORE)

    current = lambda p: match_runbook(p, store=STORE)
    legacy = lambda p: _legacy_match(p, runbooks)

    report = {
        "benchmark": "runbook-retrieval",
        "store": STORE,
        "corpus_size": len(runbooks),
        "matcher": {
            "verbatim_dataset": _score_set(verbatim, current),
            "held_out_paraphrases": _score_set(held_out, current),
        },
        "legacy_word_overlap_matcher": {
            "verbatim_dataset": _score_set(verbatim, legacy),
            "held_out_paraphrases": _score_set(held_out, legacy),
        },
    }

    if write:
        os.makedirs(BENCHMARK_DIR, exist_ok=True)
        path = os.path.join(BENCHMARK_DIR, "retrieval-round1.json")
        with open(path, "w") as f:
            json.dump(report, f, indent=2)
        report["written_to"] = path
    return report


@pytest.fixture(scope="module")
def report():
    return run_retrieval_benchmark(write=False)


def test_no_incident_is_matched_to_the_wrong_runbook(report):
    """The one error class that must never happen."""
    for split in ("verbatim_dataset", "held_out_paraphrases"):
        result = report["matcher"][split]
        assert result["wrong_unsafe"] == 0, result["failures"]


def test_accuracy_on_the_verbatim_dataset(report):
    assert report["matcher"]["verbatim_dataset"]["accuracy"] == 1.0


def test_accuracy_on_held_out_paraphrases(report):
    """The number that measures generalisation rather than memorisation."""
    assert report["matcher"]["held_out_paraphrases"]["accuracy"] >= 0.95, \
        report["matcher"]["held_out_paraphrases"]["failures"]


def test_out_of_scope_prompts_escalate(report):
    """Hardware faults, gibberish and privilege-escalation requests match nothing."""
    for prompt in ("my screen is physically cracked and the hinge is broken",
                   "random text with no meaning xyz123 qwerty",
                   "please give the account fabian full sudo rights and disable the firewall"):
        assert match_runbook(prompt, store=STORE) is None


def test_retrieval_beats_the_legacy_word_overlap_matcher(report):
    new = report["matcher"]["held_out_paraphrases"]
    old = report["legacy_word_overlap_matcher"]["held_out_paraphrases"]
    assert new["accuracy"] > old["accuracy"]
    assert new["wrong_unsafe"] <= old["wrong_unsafe"]


def test_retrieval_is_fast_enough_to_run_on_every_incident(report):
    """Retrieval must stay negligible next to the diagnostic commands."""
    for split in ("verbatim_dataset", "held_out_paraphrases"):
        assert report["matcher"][split]["latency_ms_p95"] < 15.0
