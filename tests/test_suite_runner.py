"""Round 1 benchmark: runs tests/test_suite.json through the real API and
records latency/tool-call metrics for the TDD efficiency section (rubric #4).
"""
import json
import os
import sys
import uuid
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
import src.database as db
from src.main import app
from src.database import init_db
from src.engine.incident_commander import run_incident, approve_action

SUITE_PATH = os.path.join(os.path.dirname(__file__), "test_suite.json")
BENCHMARK_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "benchmarks")


def _expected_statuses(expected: str) -> set:
    mapping = {
        "runbook_match": {"awaiting_approval", "resolved"},
        "escalate": {"escalated"},
        "blocked": {"escalated"},
        "diagnose": {"escalated"},
    }
    return mapping.get(expected, {"escalated"})


def _matches_expected(case, result) -> bool:
    expected = case["expected"]
    if expected == "blocked":
        return any(
            "injection" in e.get("message", "").lower()
            or "BLOCKED" in e.get("message", "")
            for e in result.get("events", [])
        )
    return result.get("status") in _expected_statuses(expected)


def run_round1(round_num: int = 1) -> dict:
    """Execute all test suite cases and record metrics.

    `round_num` controls the output filename (round1.json, round2.json, ...)
    so the same harness can produce both the Before (Round 1) and After
    (Round 2+) benchmark artifacts for the TDD efficiency comparison.
    """
    init_db()

    with open(SUITE_PATH) as f:
        cases = json.load(f)["test_cases"]

    results = []
    for case in cases:
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db.DB_PATH = tmp.name
        init_db()

        is_error = case["expected"] == "error"
        if is_error:
            # Validate empty input raises ValueError at the model layer
            try:
                from src.models import IncidentCreate
                IncidentCreate(user_prompt=case["prompt"])
                passed = False
            except Exception:
                passed = True
            result = {"status": "validation_error", "events": []}
            metrics_out = {}
        else:
            incident_id = f"BENCH-{uuid.uuid4().hex[:8].upper()}"
            result = run_incident(incident_id, case["prompt"])
            passed = _matches_expected(case, result)
            metrics_out = {
                "latency_ms": result.get("metrics", {}).get("latency_ms"),
                "tool_calls": result.get("metrics", {}).get("tool_calls"),
            }

        results.append({
            "id": case["id"],
            "category": case["category"],
            "description": case["description"],
            "expected": case["expected"],
            "status": result["status"],
            "passed": passed,
            **metrics_out,
        })
        os.unlink(tmp.name)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    latencies = [r["latency_ms"] for r in results if r.get("latency_ms") is not None]
    tool_calls = [r["tool_calls"] for r in results if r.get("tool_calls") is not None]

    report = {
        "round": round_num,
        "total_cases": total,
        "passed": passed_count,
        "accuracy": round(passed_count / total, 3) if total else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
        "avg_tool_calls": round(sum(tool_calls) / len(tool_calls), 2) if tool_calls else None,
        "results": results,
    }

    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    out = os.path.join(BENCHMARK_DIR, f"round{round_num}.json")
    with open(out, "w") as f:
        json.dump(report, f, indent=2)
    return report


def print_table(report: dict) -> None:
    print(f"{'ID':<8}{'Expected':<14}{'Status':<16}{'Passed':<7}{'Latency(ms)':<12}{'Tools':<6}")
    print("-" * 63)
    for r in report["results"]:
        print(
            f"{r['id']:<8}{r['expected']:<14}{r['status']:<16}"
            f"{'YES' if r['passed'] else 'NO ':<7}"
            f"{(r.get('latency_ms') or 0):<12}{r.get('tool_calls') or 0:<6}"
        )
    print("-" * 63)
    print(
        f"Accuracy: {report['accuracy']:.1%}   "
        f"Avg latency: {report['avg_latency_ms']} ms   "
        f"Avg tool calls: {report['avg_tool_calls']}"
    )


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run the benchmark suite and write data/benchmarks/roundN.json")
    parser.add_argument("--round", type=int, default=1, help="Round number for the output artifact")
    args = parser.parse_args()

    rep = run_round1(round_num=args.round)
    print_table(rep)


def test_round1_suite_all_pass():
    report = run_round1(round_num=1)
    for r in report["results"]:
        assert r["passed"], f"{r['id']} failed: expected={r['expected']} got={r['status']}"