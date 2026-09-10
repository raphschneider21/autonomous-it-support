"""Demo dry-run gate (Milestone 5).

Before recording the 15-minute live PoC, run this to confirm the whole stage
is ready: API health, client UI assets, runbook store, and every
engine-dependent demo segment executes cleanly and well inside its cadence
budget. Exits non-zero (and prints NOT READY) when anything fails.

    python tests/demo_dryrun.py

Segments 1 (opener) and 6 (deep dive) are presenter/static content and are
checked as presence-of-assets; the narration timing is tracked by the human
protocol in docs/demo-dryrun.md.
"""
import sys
import os
import time

sys.path.insert(0, os.path.dirname(__file__))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import test_demo_rehearsal  # noqa: E402  (reuses the segment executors + summary)

from fastapi.testclient import TestClient  # noqa: E402
import src.database as db  # noqa: E402
from src.database import init_db  # noqa: E402
from src.main import app  # noqa: E402

CLIENT_DIR = os.path.join(os.path.dirname(__file__), "..", "src", "client")

# Cadence targets from .agents/rules/live-demo-spec.md (HH:MM on clock)
CADENCE = [
    ("S1  Opener & Problem Framing",    "0:00-1:00",  60),
    ("S2  Incident Intake & Triage",    "1:00-4:00", 180),
    ("S3  Agent Traces & Disagreement", "4:00-7:00", 180),
    ("S4  Consent-Window Safe Execution", "7:00-9:00", 120),
    ("S5  Prompt Injection Defense",    "9:00-11:00", 120),
    ("S6  Technical Deep Dive",        "11:00-13:00", 120),
    ("S7  Measured Outcomes & Wrap",   "13:00-15:00", 120),
]
TOTAL_BUDGET_S = sum(b for _, _, b in CADENCE)


def _checks() -> list[dict]:
    results = []
    for name, path, ok, detail in [
        ("API health", "/api/health", None, ""),
        ("Runbook store populated", "/api/runbooks", None, ""),
        ("Client UI served", "/", None, ""),
    ]:
        results.append({"name": name, "ok": ok, "detail": detail, "path": path})

    with TestClient(app) as client:
        results[0]["ok"] = client.get("/api/health").status_code == 200
        rb = client.get("/api/runbooks")
        results[1]["ok"] = rb.status_code == 200 and len(rb.json()) >= 3
        results[1]["detail"] = f"{len(rb.json())} runbooks"
        ui = client.get("/")
        results[2]["ok"] = ui.status_code == 200 and "text/html" in ui.headers.get("content-type", "")
        results[2]["detail"] = ui.headers.get("content-type", "")

    for asset in ("index.html", "app.js", "style.css", "demo.html", "demo.js", "demo.css"):
        results.append({
            "name": f"UI asset: {asset}",
            "ok": os.path.exists(os.path.join(CLIENT_DIR, asset)),
            "detail": f"src/client/{asset}",
            "path": f"/static/{asset}",
        })
    return results


def run_gate() -> dict:
    tmp = tempfile = __import__("tempfile")
    t = tmp.NamedTemporaryFile(suffix=".db", delete=False)
    t.close()

    db.DB_PATH = t.name
    init_db()

    checks = []
    for c in _checks():
        with TestClient(app) as client:
            if c.get("path") and c.get("path").startswith("/static/"):
                c["ok"] = client.get(c["path"]).status_code == 200
        checks.append(c)

    os.unlink(t.name)

    rehearsal = test_demo_rehearsal.run_rehearsal()
    engine_ok = rehearsal.pop("all_ok")

    return {
        "checks": checks,
        "rehearsal": rehearsal,
        "engine_ok": engine_ok,
        "ready": engine_ok and all(c["ok"] for c in checks),
    }


def print_report(report: dict) -> None:
    print("\n=== DEMO DRY-RUN GATE ===")
    for c in report["checks"]:
        mark = "PASS" if c["ok"] else "FAIL"
        print(f"  [{mark}] {c['name']:<42} {c['detail']}")

    rehearse = report["rehearsal"]
    test_demo_rehearsal.print_summary(rehearse)

    print("\n=== CADENCE BUDGET (human pacing) ===")
    print(f"  {'Segment':<42}{'Clock':<12}{'Budget':<8}")
    for name, clock, s in CADENCE:
        print(f"  {name:<42}{clock:<12}{s}s")
    print(f"  Total narrative budget: {TOTAL_BUDGET_S}s (15:00)")

    print(f"\nVERDICT: {'READY TO RECORD' if report['ready'] else 'NOT READY'}")
    return report["ready"]


if __name__ == "__main__":
    ok = print_report(run_gate())
    sys.exit(0 if ok else 1)


def test_demo_dryrun_gate_passes():
    report = run_gate()
    print_report(report)
    assert report["ready"]
