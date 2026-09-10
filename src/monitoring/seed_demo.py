"""Loads the three canonical scenarios into a running Service Desk.

Lets this lane be developed, reviewed and demonstrated before Dev1's endpoint
branch merges. The fixtures under `tests/fixtures/service_desk/` were captured
from real engine runs, so the Service Desk renders genuine audit data rather
than hand-written sample rows.

    uvicorn src.monitoring.app:app --port 8001      # in one terminal
    python -m src.monitoring.seed_demo              # in another

Pass `--url` to target a Service Desk on another host, and `--wipe` to clear
existing tickets first.
"""
import argparse
import json
import pathlib
import sys
import urllib.error
import urllib.request

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "service_desk"

# Documentation the endpoint will send once Dev1 implements the optional
# contract fields. Attached here so the Documentation tab can be reviewed now.
CUPS_REPORT = """# Incident Report — INC-A82F91D3

**Employee reported:** Print jobs are stuck in the queue and I cannot delete them.
**Endpoint:** ubuntu-demo-01

## Findings
The CUPS print queue held two jobs that could not drain. The service was
running, so the fault was the queue rather than the daemon.

## Actions taken
1. Cleared the stuck print queue (`cancel -a`)
2. Restarted the CUPS service (`sudo systemctl restart cups`)

## Verification
`systemctl is-active cups` returned `active` and `lpstat -o` reported an empty
queue.

## Outcome
The employee confirmed the problem was solved. Ticket closed by automated
Tier 1 without human involvement.
"""

CUPS_RUNBOOK = {
    "runbook_id": "RB-CUPS-001",
    "title": "Print Queue Stuck and Nothing Prints (CUPS Backlogged)",
    "steps": [
        {"description": "Clear the stuck print queue", "command": "cancel -a"},
        {"description": "Restart the CUPS service", "command": "sudo systemctl restart cups"},
    ],
}

DOCUMENTATION = {
    "scenario_a_cups_resolved": {"incident_report": CUPS_REPORT, "runbook": CUPS_RUNBOOK},
}


def post(url: str, payload: dict) -> dict:
    request = urllib.request.Request(
        f"{url.rstrip('/')}/api/tickets",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", default="http://127.0.0.1:8001")
    parser.add_argument("--wipe", action="store_true",
                        help="delete the local ticket database before seeding")
    args = parser.parse_args()

    if args.wipe:
        from . import store
        pathlib.Path(store.DB_PATH).unlink(missing_ok=True)
        store.init_db()
        print("ticket database cleared")

    fixtures = sorted(FIXTURES.glob("*.json"))
    if not fixtures:
        print(f"no fixtures found in {FIXTURES}", file=sys.stderr)
        return 1

    for path in fixtures:
        payload = json.loads(path.read_text())
        payload.update(DOCUMENTATION.get(path.stem, {}))
        try:
            ticket = post(args.url, payload)
        except urllib.error.URLError as exc:
            print(f"cannot reach the Service Desk at {args.url}: {exc.reason}", file=sys.stderr)
            return 1
        print(f"  {ticket['incident_id']}  {ticket['display_status']:<12} "
              f"{ticket['support_level']:<13} {path.stem}")

    print(f"\nSeeded {len(fixtures)} scenarios. Open {args.url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
