"""Round 1 benchmark: runs tests/test_suite.json through the real API and
records latency/tool-call metrics for the TDD efficiency section (rubric #4).
"""
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from fastapi.testclient import TestClient
import src.database as db
from src.main import app
from src.database import init_db

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


def _matches_expected(case, response) -> bool:
    expected = case["expected"]
    if expected == "error":
        # Empty prompt must be rejected by validation (HTTP 422).
        return response.status_code == 422
    if expected == "blocked":
        return response.status_code == 200 and any(
            "injection" in e.get("message", "").lower()
            or "BLOCKED" in e.get("message", "")
            for e in response.json().get("events", [])
        )
    if response.status_code != 200:
        return False
    return response.json().get("status") in _expected_statuses(expected)


def run_round1() -> dict:
    """Execute all test suite cases through the API and record metrics."""
    init_db()
    client = TestClient(app)

    with open(SUITE_PATH) as f:
        cases = json.load(f)["test_cases"]

    results = []
    for case in cases:
        # Fresh temp DB per case keeps the audit trail isolated for evidence.
        tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp.close()
        db.DB_PATH = tmp.name
        init_db()

        payload = {"user_prompt": case["prompt"]}
        response = client.post("/api/incidents", json=payload)

        passed = _matches_expected(case, response)

        metrics = {"latency_ms": None, "tool_calls": None}
        if response.status_code == 200:
            body = response.json()
            metrics = {
                "latency_ms": body.get("metrics", {}).get("latency_ms"),
                "tool_calls": body.get("metrics", {}).get("tool_calls"),
            }

        results.append({
            "id": case["id"],
            "category": case["category"],
            "description": case["description"],
            "expected": case["expected"],
            "status_code": response.status_code,
            "status": response.json().get("status") if response.status_code == 200 else "validation_error",
            "passed": passed,
            **metrics,
        })
        os.unlink(tmp.name)

    total = len(results)
    passed_count = sum(1 for r in results if r["passed"])
    latencies = [r["latency_ms"] for r in results if r["latency_ms"] is not None]
    tool_calls = [r["tool_calls"] for r in results if r["tool_calls"] is not None]

    report = {
        "round": 1,
        "total_cases": total,
        "passed": passed_count,
        "accuracy": round(passed_count / total, 3) if total else 0.0,
        "avg_latency_ms": round(sum(latencies) / len(latencies), 1) if latencies else None,
        "max_latency_ms": max(latencies) if latencies else None,
        "avg_tool_calls": round(sum(tool_calls) / len(tool_calls), 2) if tool_calls else None,
        "results": results,
    }

    os.makedirs(BENCHMARK_DIR, exist_ok=True)
    out = os.path.join(BENCHMARK_DIR, "round1.json")
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
            f"{(r['latency_ms'] or 0):<12}{r['tool_calls'] or 0:<6}"
        )
    print("-" * 63)
    print(
        f"Accuracy: {report['accuracy']:.1%}   "
        f"Avg latency: {report['avg_latency_ms']} ms   "
        f"Avg tool calls: {report['avg_tool_calls']}"
    )


if __name__ == "__main__":
    rep = run_round1()
    print_table(rep)


# --- pytest entry (so the suite runs in CI/test runs) ---

def test_round1_suite_all_pass():
    report = run_round1()
    for r in report["results"]:
        assert r["passed"], f"{r['id']} failed: expected={r['expected']} got={r['status']}"