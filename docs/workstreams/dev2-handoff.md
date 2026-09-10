# Dev2 Integration Handoff — Service Desk

**Branch:** `feature/demo-service-desk`
**Contract:** [`dev2-service-desk.md`](./dev2-service-desk.md)
**Status:** ready for integration review. Not merged to `main`.

---

## 1. API changes

All additive. Dev1's existing ticket client works unchanged; no field was
renamed, removed, or made required.

### `POST /api/tickets` — two new optional inputs

Exactly the frozen contract names:

```json
{
  "incident_report": "<markdown text>  |  null",
  "runbook": {
    "runbook_id": "RB-CUPS-001",
    "title": "Print Queue Stuck and Nothing Prints (CUPS Backlogged)",
    "steps": [{"description": "...", "command": "..."}]
  }
}
```

Both nullable. A snapshot omitting them ingests exactly as before.

**One behaviour worth knowing:** documentation arrives late in the lifecycle and
is not repeated on every snapshot, so a later update that omits it **preserves**
what was already stored. Without that, the closing snapshot would erase the
report it had just produced. If Dev1 ever needs to *clear* documentation, that
needs a new explicit signal — flag it rather than sending `null`.

### `GET /api/tickets` and `GET /api/tickets/{id}` — six derived fields

Computed server-side so the queue, ticket detail and Live Operations cannot
disagree about ticket ownership. Nothing here is stored; all are derived from
data the endpoint already reports.

| Field | Type | Meaning |
|---|---|---|
| `support_level` | `"AUTOMATED L1"` \| `"HUMAN L2"` | `escalated` → `HUMAN L2`; everything else → `AUTOMATED L1` |
| `display_status` | `INVESTIGATING` \| `AWAITING USER` \| `CLOSED` \| `ESCALATED` | Operational wording for the stored status |
| `false_resolution` | bool | A `verification` action ran **and** the employee reported `still_broken` |
| `refused` | bool | Any action with tier `red` or type `blocked` |
| `escalation_reason` | string | One sentence; empty unless escalated |
| `escalated_from_automation` | bool | `status == "escalated"` |

Plus `runbook` (hydrated object) and `incident_report` on every ticket.

No existing field changed shape.

---

## 2. What was built

**Two modes.** *Tickets* is the IT product; *Live Operations* is the
under-the-hood technical surface, inside the same app. Live Operations commits
to a dark panel — the contrast shift signals the move from ticket product to
system internals.

**Queue.** Every row carries `AUTOMATED L1` / `HUMAN L2` beside an operational
status, so ownership reads without opening a ticket. Escalated rows get an amber
left rail, refused rows a red one.

**Ticket detail** — Overview / Timeline / Diagnostics / Documentation /
Escalation. The Escalation tab only appears on escalated tickets.

**L1 → L2 handoff.** Escalated tickets get a full-width block showing
`AUTOMATED L1` struck through, an arrow, and `HUMAN L2` with the reason. It
appears in both Overview and Escalation.

**False resolution** is a full callout, not a status field: *"Verified fixed,
but the employee still cannot work."*

**Live Operations** renders the audit trail as a component trace
(SECURITY / TRIAGE / DIAGNOSTIC / EXECUTOR / VERIFY / COMMANDER / REFUSED) at
~1rem monospace, with refusals in red and a `REFUSED BY POLICY` flag.

**Polling** at 1s (was 3s). The trace re-renders only when
`(incident, row count, status)` changes, so a poll cannot flicker the screen
mid-read.

---

## 3. Two honesty constraints, enforced in code

**Timeline stages are labelled `recorded` or `from ticket state` in the UI.** A
stage derived from ticket state (runbook applied, employee confirmation,
closure) is visually distinct from one backed by a timestamped audit entry.
Stages with no supporting entry are omitted rather than shown as pending — so
Scenario C's timeline does not imply diagnostics that never ran.

**The trace never invents rows.** One row per reported audit entry, asserted by
test (`test_the_trace_never_invents_rows`).

---

## 4. Open item for Dev1 — runbook match has no audit entry

**Problem:** `final-demo-plan.md` §5.4 shows a timestamped Live Operations line:

```text
09:42:11.139  KNOWLEDGE
              matched: cups-service-recovery
              confidence: 93%
```

The engine records the runbook match only as a streamed UI event. There is no
audit row, therefore no real timestamp and no confidence value in the ticket
payload.

**Why it matters:** rendering that line as specified means fabricating a
timestamp on the surface presented as the audit trail.

**Recommended:** one audit entry at match time in the Incident Commander —
`action_type="runbook_match"`, `command=None`, output carrying `runbook_id` and
the matcher's confidence. `runbook_matcher` already computes confidence.

**Impact:** Dev1 only, additive, no contract change. The Service Desk needs no
change — `KNOWLEDGE` is already in `COMPONENT_BY_ACTION`, so the row upgrades
from untimed context to a timestamped trace entry automatically.

**Current behaviour:** shown as an untimed `KNOWLEDGE` context row.

---

## 5. Manual acceptance — works without Dev1's branch

```bash
uvicorn src.monitoring.app:app --host 0.0.0.0 --port 8001    # terminal 1
python -m src.monitoring.seed_demo --wipe                    # terminal 2
open http://localhost:8001
```

Fixtures under `tests/fixtures/service_desk/` were captured from **real engine
runs**, not hand-written, so the UI renders genuine audit data.

| # | Step | Expect |
|---|---|---|
| 1 | Queue | Three rows; ownership and status readable without opening one |
| 2 | `INC-A82F91D3` → Documentation | Incident report marked *generated for this incident*; runbook marked *pre-existing knowledge* |
| 3 | `INC-A82F91D3` → Timeline | Recorded stages timestamped; *Runbook applied* and *Employee confirmation* marked `from ticket state` |
| 4 | `INC-B31902F1` → Overview | False-resolution callout + L1 → L2 handoff block |
| 5 | `INC-B31902F1` → Escalation | Everything already attempted, plus verification that passed |
| 6 | `INC-C281AD72` → Diagnostics | Refusal listed first; *"No commands were executed on the endpoint"* |
| 7 | Live Operations | Trace renders; switch tickets and confirm the header follows |

---

## 6. Tests

**32 monitoring tests** in `tests/test_service_desk.py`; **583 in the repo**, all
passing.

Covers: partial ingestion, idempotent updates, documentation persistence and
survival across partial snapshots, ownership derivation for every status,
`still_broken` → `HUMAN L2`, refusal flagging, trace fidelity, timeline
recorded-vs-inferred labelling, progressive multi-snapshot incidents, trace-key
change detection, empty ticket, empty desk, and malformed action entries.

---

## 7. Known limitations

1. **No browser verification.** Browser tooling was unavailable this session, so
   the UI was verified structurally — all DOM ids resolve, no unstyled
   selectors, assets serve, every field each tab needs is present for all three
   scenarios — but **not visually**. Two judgements need a human: whether the
   Live Operations trace is large enough for classroom projection, and whether
   the L1→L2 block reads as the "automation knew when to stop" moment rather
   than as another error state.
2. **Live Operations tested against stored progressive snapshots, not a running
   endpoint.** The update path is asserted by test; the end-to-end feel with
   Dev1's real reporting cadence is unverified.
3. **`KNOWLEDGE` row is untimed** until Dev1 adds the audit entry (§4).
4. **Token metrics read 0** on deterministic demo runs. Labelled *"none —
   deterministic run"* rather than shown as a zero cost, and engine latency is
   labelled "Engine latency" so it cannot be mistaken for human resolution time.

---

## 8. Lane boundaries

`git diff --name-only main...HEAD` touches only:

```text
src/monitoring/**
tests/test_service_desk.py
tests/fixtures/service_desk/**
docs/workstreams/dev2-handoff.md   (this file)
```

No endpoint, engine, executor, safety or employee-UI file was modified.
`src/integrations/monitoring_client.py` was read but not changed.
