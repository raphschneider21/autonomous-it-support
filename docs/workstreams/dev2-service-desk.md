# Dev2 Workstream Contract — Service Desk, Ticket Experience & Live Operations

**Branch:** `feature/demo-service-desk`  
**Parent plan:** `docs/final-demo-plan.md`  
**High-level split:** `docs/workstreams/README.md`

## 1. Mission

Turn the existing monitoring application into the polished central-IT half of the final demo.

Dev2 owns what the IT technician and the technical audience see on the Mac: the ticket queue, ticket detail, L1→L2 ownership handoff, documentation, escalation information, and the Live Operations view.

This lane should refine and extend the current Service Desk rather than replace it with a new application or external ITSM platform.

---

## 2. Definition of done

Dev2 is done when all of the following are true:

1. New endpoint incidents appear promptly in the Service Desk.
2. The queue clearly communicates ticket status and ownership, especially `AUTOMATED L1` versus `HUMAN L2`.
3. A ticket detail view can explain what happened without requiring the audience to inspect raw JSON or source code.
4. The IT view contains the frozen information areas: Overview, Timeline, Diagnostics, Documentation, and Escalation.
5. Live Operations presents actual received agent/audit activity in an audience-readable technical trace.
6. The `still_broken` path visibly changes a ticket from automated Tier 1 to human Tier 2.
7. Prompt-injection/refusal events are visually obvious and show that no unsafe remediation was performed.
8. The Service Desk remains useful if some optional fields are absent or arrive later in the incident lifecycle.
9. Existing monitoring APIs remain backward-compatible with Dev1's ticket-reporting client.
10. The page is polished enough to be one of the main presentation surfaces in a recorded 15-minute demo.

---

## 3. Files and areas owned by this lane

Dev2 may modify these areas as needed:

- `src/monitoring/app.py`
- `src/monitoring/store.py`
- `src/monitoring/client/**`
- monitoring-specific tests under `tests/**`
- monitoring-specific helper modules placed under `src/monitoring/**`

Dev2 should avoid modifying:

- `src/client/**` — Dev3 owns the employee and Demo Lab frontend.
- `src/executors/**` — Dev1 owns endpoint simulation/runtime.
- `src/engine/**` — Dev1 owns runtime/scenarios.
- `src/main.py` — Dev1 owns endpoint FastAPI changes.
- `src/integrations/monitoring_client.py` — Dev1 owns the sending side of the shared ticket contract.
- `docs/final-demo-plan.md` — frozen product contract.

If a Service Desk requirement appears to need an endpoint-side change, implement the Mac side against the frozen contract and raise the endpoint change instead of editing Dev1's files.

---

## 4. Shared ticket ingestion contract

The Service Desk continues to accept repeated idempotent updates for one `incident_id` through:

```text
POST /api/tickets
```

Existing fields remain supported:

```json
{
  "incident_id": "INC-1234ABCD",
  "hostname": "ubuntu-demo-01",
  "title": "My printer isn't printing anything.",
  "status": "open",
  "category": "printing",
  "severity": "medium",
  "user_prompt": "My printer isn't printing anything.",
  "runbook_id": "RB-CUPS-001",
  "resolution": null,
  "agent_source": null,
  "latency_ms": null,
  "tool_calls": null,
  "tokens_in": 0,
  "tokens_out": 0,
  "actions": [],
  "errors": [],
  "escalation": null,
  "user_confirmed": null
}
```

Dev2 must additionally support these optional fields when Dev1 sends them:

```json
{
  "incident_report": "<human-readable report text or null>",
  "runbook": {
    "runbook_id": "RB-CUPS-001",
    "title": "Print Queue Stuck and Nothing Prints (CUPS Backlogged)",
    "steps": []
  }
}
```

Rules:

- both new fields are optional and nullable;
- older/partial ticket updates must still ingest successfully;
- an update for an existing `incident_id` must update the ticket, not create a duplicate;
- Service Desk storage must persist the optional documentation fields if received;
- do not require access to the Ubuntu endpoint filesystem to display documentation.

---

## 5. Ticket ownership semantics

The final demo must make support ownership obvious.

Use these product labels:

```text
AUTOMATED L1
HUMAN L2
```

The minimum ownership rule can be derived from ticket state:

- `open`, `diagnosing`, or technically resolved but awaiting the user's confirmation → `AUTOMATED L1`;
- `closed` → final owner may remain labelled `AUTOMATED L1` with `RESOLVED/CLOSED` status;
- `escalated` → `HUMAN L2`.

For the `still_broken` path, the UI must create a clear visual transition:

```text
AUTOMATED L1
     ↓
 HUMAN L2
```

Do not make the audience infer the handoff from a small `escalated` pill alone.

---

## 6. Ticket queue contract

The queue is the opening IT view and should be presentation-readable from a normal laptop/recording resolution.

Each ticket row/card should prioritise:

- incident id;
- concise issue title;
- endpoint;
- category if useful;
- current support owner (`AUTOMATED L1` / `HUMAN L2`);
- state (`INVESTIGATING`, `AWAITING USER`, `CLOSED`, `ESCALATED`, etc.);
- prominent indicator for security/refusal or user-reported unresolved state where applicable.

Existing summary metrics can remain, but they must not dominate the demo. Prefer meaningful operational metrics such as open/closed/escalated, auto-resolution, false-resolution, and measured latency over decorative dashboard numbers.

The current three-second polling cadence may be shortened for presentation responsiveness. A full streaming redesign is not required; simple frequent polling is acceptable if reliable.

Target perceived behaviour: when the Ubuntu endpoint creates an incident, the ticket should appear on the Mac quickly enough that the presenter does not stand waiting for the UI.

---

## 7. Ticket detail information architecture

The frozen target is:

```text
Overview | Timeline | Diagnostics | Documentation | Escalation
```

Tabs, segmented controls, or another polished equivalent are acceptable, but the information categories must remain obvious.

### Overview

Show, where available:

- incident id;
- current status;
- current support owner;
- employee report;
- endpoint/hostname;
- category;
- severity;
- runbook matched;
- technical resolution summary;
- user confirmation (`solved`, `still_broken`, or pending);
- key measured values such as latency/tool calls only if they improve the story.

### Timeline

Create a chronological incident story from received `actions`, `errors`, status changes, and available timestamps.

The audience should be able to follow:

```text
Incident opened
→ security/input check
→ triage
→ diagnostics
→ knowledge/runbook decision
→ remediation/refusal
→ verification
→ user confirmation
→ close or L2 escalation
```

Do not fabricate missing timestamps or steps. If a lifecycle event is inferred from ticket state rather than explicitly received, label/present it conservatively.

### Diagnostics

Show technical actions and outputs in a readable structured format.

Prioritise:

- command/tool invoked;
- which component/agent invoked it;
- safety tier/policy outcome;
- concise output;
- success/refusal/error state.

Avoid making the main view a wall of JSON.

### Documentation

When present, show:

**Incident Report**
- human-readable report generated from the incident execution;
- preserve line breaks/Markdown readability;
- clearly identify it as incident-specific generated documentation.

**Operational Runbook**
- identify runbook id/title;
- show relevant steps in a readable representation;
- clearly identify it as pre-existing machine-readable operational knowledge used by the system.

If the full optional payload has not yet arrived, degrade gracefully to the existing `runbook_id` and a useful empty/pending state.

### Escalation

When a ticket is escalated, summarise the handoff for a human technician:

- why it escalated;
- user report;
- attempted diagnostics/remediations;
- verification result;
- user verdict where applicable;
- security/refusal context;
- structured escalation payload.

Raw JSON may be available behind a `View raw payload` control, but it should not be the primary presentation.

---

## 8. Live Operations contract

Live Operations is the primary technical/under-the-hood view shown during the presentation.

It lives inside the Service Desk application rather than becoming a separate service.

It should display the selected or currently active ticket in a large, terminal-inspired but purpose-built trace.

Minimum visible concepts:

- current incident id;
- endpoint;
- mode/context where known;
- agent/component identity;
- chronological actions;
- commands/tool calls;
- outputs/evidence;
- safety tier/refusal;
- runbook/knowledge match if available;
- verification;
- final Commander/terminal state.

Example visual structure:

```text
LIVE OPERATIONS                              INC-1042
Endpoint: ubuntu-demo-01
Status: INVESTIGATING

09:42:11  SECURITY
          Input policy check                     PASS

09:42:11  TRIAGE
          category: printing

09:42:12  DIAGNOSTIC
          $ systemctl is-active cups
          → inactive

09:42:12  EXECUTOR
          $ sudo systemctl restart cups
          → permitted

09:42:13  VERIFY
          $ systemctl is-active cups
          → active
```

The view must render **received real ticket/audit data**, not a second scripted animation that can disagree with the backend.

If events arrive only as polling snapshots, diff/update the rendered trace cleanly rather than duplicating rows on every poll.

---

## 9. Canonical demo behaviours the UI must support

### Scenario A — CUPS success

Service Desk should visibly show:

- new ticket appears while endpoint investigation is active;
- Live Operations fills with agent/activity evidence;
- CUPS-related diagnosis/remediation/verification is readable;
- ticket remains automated L1;
- after user confirms success, ticket becomes closed/resolved;
- incident documentation is accessible.

### Scenario B — user says Still Broken

Service Desk should visibly show:

- technical verification can have passed;
- user confirmation becomes `still_broken`;
- ticket becomes escalated;
- ownership changes to `HUMAN L2`;
- a strong callout explains that technical verification succeeded but the employee still cannot work;
- the L2 technician can see everything already attempted.

This is a major business-demo moment and should receive strong visual treatment.

### Multi-agent disagreement

Where received in the ticket actions/audit trail, make contrasting Diagnostic/Security assessments and the Commander/reconciliation decision readable. Do not invent dialogue that is absent from the payload.

### Scenario C — prohibited/prompt-injection input

Service Desk should visibly show:

- security/refusal status;
- zero remediation execution if that evidence is available;
- the red/refused action(s) clearly separated from ordinary diagnostic activity;
- escalation/security handoff.

---

## 10. Visual and presentation requirements

The Service Desk is a keynote-style demonstration surface, not an internal admin prototype.

Requirements:

- readable at 1920×1080 screen recording;
- strong visual hierarchy;
- meaningful status colours/badges without depending on colour alone;
- large enough ticket rows and trace text for viewers at the back of a classroom;
- no accidental horizontal scrolling in the primary demo views;
- polished empty/loading/error states;
- clear selected-ticket state;
- no modal/alert spam for normal navigation;
- avoid excessive tiny metrics or dense raw developer data;
- keep interaction predictable and low-click during presentation.

Dev2 may redesign the existing CSS/HTML substantially inside `src/monitoring/client/**` as long as the frozen product information remains intact.

---

## 11. Test requirements

Add/update monitoring tests covering at least:

- partial ticket ingestion remains valid;
- repeated report for same incident is idempotent/update-in-place;
- optional `incident_report` persists and is returned;
- optional `runbook` persists and is returned;
- `resolved` without user confirmation does not falsely become final closed if current service semantics require confirmation;
- `solved` results in closed state;
- `still_broken` results in escalated state/Human L2 semantics;
- security/refusal actions survive storage/hydration;
- ticket list/detail APIs continue working with old tickets lacking the new optional fields;
- stats do not break when documentation fields are absent.

Frontend-specific automated tests are optional if the project has no browser-test framework. Manual acceptance steps must then be documented in the PR.

---

## 12. Handoff boundaries

### Dev2 can assume Dev1 will provide

- early and repeated ticket snapshots for active incidents;
- chronological `actions`/`errors` data;
- final confirmation/escalation update;
- optional `incident_report` and `runbook` fields using the frozen names.

Dev2 should build graceful states for those optional fields even before Dev1's branch is merged.

### Dev2 must provide to integration

- backward-compatible `POST /api/tickets` ingestion;
- `GET /api/tickets` and `GET /api/tickets/{incident_id}` containing all persisted display data;
- an IT UI that works even when the endpoint is temporarily offline after the ticket has been received.

Dev3 has no direct dependency on Dev2's implementation.

---

## 13. PR acceptance checklist

Before requesting integration, Dev2's PR must include:

- screenshots or a short description of Queue, Ticket Detail, and Live Operations states;
- confirmation of the L1→L2 handoff presentation;
- confirmation that old/partial tickets still render;
- API schema changes, if any, documented explicitly;
- tests run and results;
- manual steps to demonstrate Scenario A, Scenario B, and Scenario C using stored/sample ticket data if Dev1 is not yet merged;
- confirmation that no endpoint/engine files were changed without prior agreement;
- any presentation limitations still known.

Do not merge directly to `main`; return the branch/PR for integration review.