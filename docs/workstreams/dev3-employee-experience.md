# Dev3 Workstream Contract — Employee Experience & Demo Lab Frontend

**Branch:** `feature/demo-employee-experience`  
**Parent plan:** `docs/final-demo-plan.md`  
**High-level split:** `docs/workstreams/README.md`

## 1. Mission

Create the polished Ubuntu-side experience used during the final demo.

Dev3 owns two visible surfaces:

1. the **Employee Support UI** used by the fictional employee reporting an IT problem; and
2. the **Demo Lab UI** used by the presenter to inject/reset safe simulated Ubuntu faults before demonstrating the repair.

This lane is deliberately isolated from the engine and monitoring internals. Dev3 should be able to complete the work by consuming stable HTTP/SSE APIs rather than editing backend logic.

---

## 2. Definition of done

Dev3 is done when all of the following are true:

1. An ordinary employee can understand how to report a problem without seeing engineering jargon.
2. The troubleshooting consent/scope is understandable and honest about what the PoC can and cannot do.
3. The progress view communicates that the system is working without dumping raw internal traces on the employee.
4. Successful, escalated, and blocked outcomes are visually distinct and clear.
5. The user can confirm `Yes, solved` or `Still broken`, and those actions use the existing backend endpoint rather than browser-only fake alerts.
6. The Demo Lab provides working controls driven by Dev1's `/api/demo/*` contract.
7. Demo Lab shows the real simulated state returned by the backend and can reset to a known baseline.
8. No Demo Lab control is shown as functional if the backend does not report that fault in `available_faults`.
9. Both surfaces are polished enough for a 1920×1080 recorded presentation.
10. Dev3's work does not require changes to engine, executor, database, or Service Desk internals.

---

## 3. Files and areas owned by this lane

Dev3 may modify these areas as needed:

- `src/client/index.html`
- `src/client/app.js`
- `src/client/style.css`
- new Employee/Demo Lab frontend files under `src/client/**`, for example:
  - `src/client/demo.html`
  - `src/client/demo.js`
  - shared frontend components/helpers
  - additional CSS files if useful
- frontend-specific assets stored under `src/client/**`
- frontend-specific tests if a lightweight existing test approach is available

Dev3 should **not** modify:

- `src/main.py` — Dev1 owns endpoint routes/backend integration.
- `src/engine/**`
- `src/executors/**`
- `src/database.py`
- `src/integrations/**`
- `src/monitoring/**`
- Ubuntu runbooks/fixtures unless explicitly asked by the demo owner.
- `docs/final-demo-plan.md`

If a frontend need appears to require a backend change, record the exact desired behaviour/API and raise it. Do not solve it by editing backend code silently.

---

## 4. Existing endpoint APIs Dev3 can rely on

The Employee Support UI already has these backend contracts:

### Create incident

```text
POST /api/incidents
Content-Type: application/json

{
  "user_prompt": "My printer isn't printing anything."
}
```

Expected response shape:

```json
{
  "incident_id": "INC-1234ABCD",
  "status": "diagnosing"
}
```

### Follow live progress

```text
GET /api/incidents/{incident_id}/events
```

This is a Server-Sent Events stream with:

```text
event: event
```

for progress items and:

```text
event: done
```

for the terminal technical result.

The frontend must tolerate additional fields in event payloads and should present only employee-relevant information on the employee screen.

### Confirm outcome

```text
POST /api/incidents/{incident_id}/confirm
Content-Type: application/json

{ "solved": true }
```

or:

```json
{ "solved": false }
```

The returned status determines whether the ticket closes or escalates.

### Endpoint health

```text
GET /api/health
```

This can be used for a small presenter/debug indicator if useful, but the employee UI should not become a deployment dashboard.

---

## 5. Frozen Demo Lab API Dev3 must consume

Dev1 owns implementation of these APIs. Dev3 owns how they are presented.

### `GET /api/demo/state`

Required example shape:

```json
{
  "endpoint": "ubuntu-demo-01",
  "mode": "simulated",
  "available_faults": [
    {
      "id": "cups_stopped",
      "label": "CUPS printing service stopped",
      "category": "printing"
    }
  ],
  "active_faults": ["cups_stopped"],
  "services": {
    "cups": "inactive"
  }
}
```

### `POST /api/demo/faults/{fault_id}`

Injects a fault and returns the updated state object.

### `POST /api/demo/reset`

Restores the healthy deterministic baseline and returns the updated state object.

### Frontend rules

- Build fault buttons from `available_faults`; do not invent backend-only IDs.
- Highlight active faults using `active_faults`/service state.
- Always make `Reset Endpoint` available once the API is reachable.
- Show a clear error if Demo Lab cannot reach the backend.
- Never imply the buttons are damaging real Ubuntu services. The page should clearly say the endpoint is simulated/mock-backed.

---

## 6. Employee Support information architecture

The Employee Support UI should feel like a simple internal support product, not an engineering console.

Recommended flow:

```text
1. Report issue
2. Consent / scope
3. Investigating
4. Result
5. Employee confirmation
```

A multi-screen or single-page step flow is acceptable. The interaction should be predictable and require very few clicks.

### Screen/state A — Report issue

Primary content:

- clear support heading;
- short explanation such as "Describe what is not working";
- large text input;
- useful example placeholder;
- one strong primary action.

Avoid showing agent names, token counts, runbook IDs, raw safety tiers, terminal commands, or architecture terminology here.

### Screen/state B — Consent and scope

Before automated troubleshooting begins, clearly explain the scope.

The copy should communicate that the support assistant may:

- inspect approved simulated system/service information;
- run approved troubleshooting actions within the demo environment;
- record actions in the support ticket.

It should also communicate that:

- personal files are not part of the demonstrated troubleshooting scope;
- unsafe/unapproved actions remain blocked;
- this is a PoC/simulated endpoint environment where appropriate to the presenter/demo context.

The employee should have a clear start/continue action and a cancel path.

Do not reintroduce the old per-command approval modal. The frozen demo uses one up-front troubleshooting consent with policy enforcement underneath.

### Screen/state C — Investigating

The current UI exposes a raw event feed. Replace that employee-facing experience with concise understandable progress.

Examples of acceptable employee-level messages:

```text
✓ Support request received
✓ Checking printing services
✓ Problem identified
• Applying an approved fix
• Verifying the result
```

The frontend may map raw agent events to friendlier categories. Do not fabricate a completed step before the backend has actually emitted evidence for it.

A subtle "technical details" disclosure is optional, but the main employee view must remain nontechnical.

### Screen/state D — Technical result

For a successful technical result, clearly show:

- issue appears fixed;
- short plain-English resolution summary if available;
- incident id;
- prompt asking whether the employee's real problem is solved.

For an escalated result, clearly show:

- human IT support is required;
- ticket/incident id;
- the employee does not need to repeat the entire story because the attempted work has been attached.

For a blocked/security result, clearly show:

- the requested action could not be performed because it violates support/security policy;
- the case was recorded/escalated as appropriate;
- avoid accusatory or dramatic language.

### Screen/state E — Employee confirmation

Two clear actions:

```text
Yes, problem solved
Still broken
```

Both must call the real `/confirm` backend endpoint.

After `solved=true`, show a clean closed/success state before allowing a new incident.

After `solved=false`, show a clean handoff state such as:

```text
Escalated to human IT support
Ticket INC-1234ABCD
The diagnostics and attempted fixes have already been attached.
```

Avoid browser `alert()` as the main user experience.

---

## 7. Employee-facing event mapping

Dev3 does not need to understand every internal action type. Build a small robust mapping layer that converts known events to employee-friendly messages and gracefully handles unknown events.

Principles:

- prefer generic truthful messages over exposing raw internals;
- never show raw command strings by default;
- never display model confidence numbers to the employee;
- never show an internal agent disagreement as if the system is malfunctioning;
- unknown event types may map to a neutral "Continuing investigation…" or be omitted if they add no user value;
- final status always comes from the backend `done` payload, not from frontend guessing.

The technical evidence remains available on Dev2's Live Operations screen.

---

## 8. Demo Lab information architecture

Demo Lab is deliberately different from Employee Support. It is a presenter/testing tool and may show technical labels.

Recommended layout:

```text
UBUNTU ENDPOINT LAB
Endpoint: ubuntu-demo-01
Mode: SIMULATED

Printing (CUPS)        ● Healthy
DNS                    ● Healthy
Storage                ● Healthy
...

Available fault scenarios
[ Stop CUPS / Inject printing failure ]
...

[ Reset Endpoint ]
```

Only show services/faults that the API actually returns.

For the hero demo, it must be easy to perform this sequence without typing commands:

```text
Reset Endpoint
→ confirm Printing is Healthy
→ Inject CUPS failure
→ confirm Printing becomes Faulted/Inactive
→ switch to Employee Support
```

After the agent repairs the simulated CUPS fault, refreshing/polling the Demo Lab should show CUPS healthy again.

A lightweight automatic refresh/poll is preferred so state changes are visible without manual page reloads.

---

## 9. Canonical demo behaviours the frontend must support

### Scenario A — CUPS success

The presenter can:

1. open Demo Lab;
2. reset endpoint;
3. inject `cups_stopped`;
4. open Employee Support;
5. submit the fixed rehearsed printing complaint;
6. watch understandable progress;
7. see a successful technical result;
8. click `Yes, problem solved`;
9. see a final closed/success state.

### Scenario B — Still Broken

The presenter can complete a technically successful incident and click:

```text
Still broken
```

The Employee UI must then make the L2 handoff clear and preserve/display the incident id.

The Mac Service Desk owns the detailed L1→L2 visualisation; the employee only needs to understand that human IT is taking over.

### Scenario C — prohibited/prompt-injection request

When the rehearsed unsafe input is submitted, the frontend must show the backend's blocked/escalated outcome without accidentally describing it as a successful repair.

---

## 10. Visual and accessibility requirements

The Employee UI and Demo Lab are presentation surfaces.

Requirements:

- readable at 1920×1080 recording resolution;
- clean spacing and hierarchy;
- large interaction targets;
- status should not rely on colour alone;
- no tiny raw log text as the primary employee experience;
- responsive enough for the Ubuntu VM browser window used in the demo;
- no horizontal scrolling in normal demo states;
- clear loading, offline/error, success, escalation, and blocked states;
- keyboard/focus basics should not be broken;
- avoid excessive animations that can cause timing problems during recording;
- avoid dependence on third-party CDNs or web fonts that may fail offline.

The UI may be visually ambitious, but reliability and readability win over decorative complexity.

---

## 11. Local development without Dev1 being finished

Dev3 should not wait for Dev1's branch.

Until the Demo Lab backend exists locally, the frontend can be developed against:

- a tiny local mock object in JavaScript behind a clearly marked development-only fallback; or
- Dev1's frozen response example in this contract.

Before PR handoff, however, the real `/api/demo/*` endpoints must be tested if Dev1's branch is available. Development-only fake state must not silently become the production/demo path.

The Employee UI can already be developed against the existing incident/SSE/confirmation APIs on the branch baseline.

---

## 12. Test and manual acceptance requirements

At minimum verify manually and document results for:

- empty issue text cannot accidentally start an incident;
- create incident succeeds and incident id is retained;
- SSE progress renders without duplicate/broken UI;
- successful `done` state reaches employee confirmation screen;
- `Yes, solved` calls the backend and renders success;
- `Still broken` calls the backend and renders human-handoff state;
- escalated/blocked technical result does not show the solved-confirmation prompt incorrectly;
- Demo Lab renders all `available_faults` returned by backend;
- fault injection updates visible state;
- reset restores visible healthy state;
- API failure produces a readable retry/error state instead of a broken page;
- the employee UI never exposes raw unsafe command execution as a suggested manual action.

If lightweight frontend tests are practical in the existing stack, add them. Do not introduce a large new frontend framework solely to test this school-project UI.

---

## 13. Handoff boundaries

### Dev3 can assume Dev1 will provide

```text
POST /api/incidents
GET  /api/incidents/{id}/events
POST /api/incidents/{id}/confirm
GET  /api/demo/state
POST /api/demo/faults/{fault_id}
POST /api/demo/reset
```

The first three already exist on the shared baseline. The final three are frozen for Dev1 to implement.

### Dev3 does not depend directly on Dev2

The Ubuntu Employee/Demo Lab surfaces and the Mac Service Desk communicate through backend services, not through shared frontend code.

That separation is intentional so Dev3 can work independently.

---

## 14. PR acceptance checklist

Before requesting integration, Dev3's PR must include:

- screenshot(s) or short recording of Employee intake, investigation, success, escalation, and Demo Lab states;
- confirmation that employee confirmation buttons call the backend;
- confirmation that browser `alert()` is not the primary success/escalation experience;
- confirmation that Demo Lab controls are generated from backend `available_faults`;
- manual acceptance results from section 12;
- any temporary development-only mock removed or explicitly documented;
- confirmation that no engine/executor/monitoring files were modified without prior agreement;
- any remaining UX limitation relevant to the live presentation.

Do not merge directly to `main`; return the branch/PR for integration review.