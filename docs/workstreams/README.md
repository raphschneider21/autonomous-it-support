# Final Demo Workstreams

**Status:** FROZEN HIGH-LEVEL SPLIT  
**Parent plan:** `docs/final-demo-plan.md`

This document divides the remaining final-demo work into three independent developer lanes. The detailed human briefs, AI-assistant prompts, acceptance criteria, and step-by-step instructions are defined separately in the next project step.

The purpose of this split is to let all three developers work in parallel with minimal file overlap and minimal need to wait on another developer.

---

## Shared rules

1. `docs/final-demo-plan.md` is the authoritative product/demo decision document. Individual workstreams must not redesign it.
2. Nobody works directly on `main`. Each developer works on the branch assigned below.
3. Each workstream owns its files. If a developer believes a file owned by another lane must change, raise it to the demo owner rather than editing it silently.
4. Shared API contracts are treated as stable interfaces. A developer may build against the contract even while the other side is still being implemented.
5. The graded demo remains mock-backed/deterministic unless the frozen demo plan is explicitly changed.
6. Each lane must leave its part testable and demoable in isolation where practical.
7. Cross-cutting final integration, rehearsal, and TDD reconciliation happen after the three lanes return.

---

# Dev1 — Demo Runtime, Scenarios & Reliability

**Branch:** `feature/demo-runtime-reliability`

## Mission

Make the demo behaviour deterministic, stateful, safe, reproducible, and easy to launch. Dev1 owns the machinery that makes the three canonical scenarios actually work every time.

## Primary responsibilities

- Create the Ubuntu-focused stateful demo endpoint model used by `MockExecutor`.
- Replace/retire the old Windows-spooler-specific demo state where it conflicts with the Ubuntu demo story.
- Implement the canonical CUPS/printing success scenario.
- Implement deterministic state transitions so diagnostics observe the injected fault, remediation changes state, and verification observes the repaired state.
- Provide the backend API used by Demo Lab to read, inject, and reset demo state.
- Ensure the escalation / disagreement / safety scenarios behave predictably in demo mode.
- Make endpoint-to-Service-Desk reporting happen at useful lifecycle points so the IT side can display the incident and its trace.
- Ensure the data sent to the Service Desk contains the evidence required by the frozen demo plan.
- Build/reset/preflight behaviour for reliable rehearsals and recording.
- Create or refine launch scripts for the Ubuntu endpoint and overall demo readiness.
- Grow the automated demo rehearsal into a regression contract for the final scenarios.

## Primary file ownership

Dev1 owns changes in:

- `src/executors/**`
- `src/engine/**` where required for deterministic demo behaviour
- `src/main.py`
- `src/config.py` where required for explicit demo mode
- demo-state backend modules added under `src/demo/**` or equivalent
- relevant `fixtures/**` for canonical demo behaviour
- demo/runtime tests such as `tests/test_demo_*`, executor/demo-state tests, and scenario tests
- launch/preflight scripts added for the endpoint/demo runtime

Dev1 must not redesign the employee-facing UI in `src/client/**` or the Service Desk UI in `src/monitoring/**`.

---

# Dev2 — Service Desk, Ticket Experience & Live Operations

**Branch:** `feature/demo-service-desk`

## Mission

Turn the existing monitoring application into a polished central-IT product that makes the business value, escalation handoff, documentation, safety evidence, and under-the-hood behaviour immediately understandable to the audience.

## Primary responsibilities

- Refine the existing Service Desk rather than replacing it.
- Make support ownership visually explicit: `AUTOMATED L1` versus `HUMAN L2`.
- Make the L1 → L2 handoff visually obvious on escalated tickets.
- Improve ticket queue readability and presentation quality.
- Build/refine ticket detail around the frozen information architecture: Overview, Timeline, Diagnostics, Documentation, Escalation.
- Present the operational runbook and generated incident documentation accurately.
- Present previous attempts, outputs, verification and the user's final verdict so a Tier-2 technician can start from evidence.
- Build the polished `Live Operations` view inside the Service Desk.
- Reuse real ticket/audit/action data rather than inventing a second contradictory trace.
- Make safety/refusal events highly legible.
- Improve update responsiveness for stage presentation; avoid an awkward multi-second wait for ticket changes where practical.
- Preserve useful metrics such as auto-resolution and false-resolution without overstating what they prove.
- Extend the monitoring ticket schema/store only as required by the frozen demo information needs.

## Primary file ownership

Dev2 owns changes in:

- `src/monitoring/**`
- Service Desk tests, primarily `tests/test_monitoring.py` and new monitoring/UI contract tests
- monitoring-side schema/persistence changes

`src/integrations/monitoring_client.py` is a shared boundary file. Dev2 may propose payload/schema additions, but changes that affect endpoint reporting behaviour must be coordinated with Dev1 or the demo owner rather than independently changing the contract.

Dev2 must not redesign the employee UI or the endpoint simulation.

---

# Dev3 — Employee Experience & Demo Lab Frontend

**Branch:** `feature/demo-employee-experience`

## Mission

Make the Ubuntu-side experience clear, polished, and presentation-ready. Dev3 owns what the employee sees and the presenter-facing Demo Lab interface used to create/reset demo faults.

This lane is deliberately bounded around visible product surfaces and stable APIs so the developer does not need to understand the internal agent engine, Git internals, or backend architecture to contribute meaningful work.

## Primary responsibilities

### Employee Support

- Redesign/refine the current employee-facing UI into a simple product journey.
- Keep technical agent noise out of the ordinary employee view.
- Make consent/troubleshooting scope clear in plain language.
- Show understandable progress while diagnosis runs.
- Make resolved and escalated outcomes visually unmistakable.
- Keep the `Yes, problem solved` / `No, still broken` confirmation flow clear and reliable from the user's perspective.
- Show the incident/ticket identifier so the employee and Service Desk story connects visually.
- Handle normal UI states gracefully: empty input, loading, connection problem, resolved, escalated, reset/new incident.

### Demo Lab frontend

- Build the presenter-only Demo Lab page against the frozen demo-state API.
- Show the simulated Ubuntu endpoint and current health/fault state clearly.
- Provide obvious controls to inject the approved demo faults.
- Provide a prominent reset-to-healthy action.
- Make it impossible to confuse the Demo Lab with the employee-facing product.
- Do not issue real operating-system commands from the browser.

## Primary file ownership

Dev3 owns changes in:

- `src/client/**`
- new employee-side Demo Lab HTML/CSS/JS assets under `src/client/**` or a dedicated frontend-only directory agreed in the detailed workstream contract
- frontend-focused tests that do not require modifying engine internals

Dev3 does **not** need to edit `src/main.py`, `src/engine/**`, `src/executors/**`, `src/monitoring/**`, or understand those internals. The AI assistant should treat the backend APIs as a service contract and guide the human explicitly through every development-tool step needed.

---

# Frozen cross-workstream API boundaries

These interfaces exist specifically so the lanes can work in parallel.

## Employee Support → endpoint API

Existing core interfaces remain the baseline:

- `POST /api/incidents` — submit a user problem
- `GET /api/incidents/{incident_id}/events` — receive incident progress via SSE
- `GET /api/incidents/{incident_id}` — retrieve incident/audit detail when needed
- `POST /api/incidents/{incident_id}/confirm` — submit `solved` / `still broken`
- `GET /api/health` — endpoint/demo-mode health information

Dev3 builds against these without changing their backend semantics.

## Demo Lab → demo-state API

Dev1 will provide the following stable behaviour for Dev3 to consume:

- `GET /api/demo/state` — return current simulated endpoint state
- `POST /api/demo/faults/{fault_id}` — inject one approved deterministic demo fault
- `POST /api/demo/reset` — reset the simulated endpoint to the known healthy baseline

Responses should be JSON and return the updated state so the frontend can render without guessing.

The minimum initial fault ID is the printing/CUPS hero scenario. Additional fault IDs may be added for the final escalation scenario if required.

## Endpoint → Service Desk

The existing HTTP ticket-ingestion architecture remains the baseline:

- endpoint reports to the configured monitoring URL;
- Service Desk accepts idempotent updates for the same `incident_id`;
- updates may arrive repeatedly as the incident progresses;
- reporting failure never blocks endpoint troubleshooting.

The minimum ticket data needed by the final demo includes:

- incident ID and endpoint identity;
- employee report;
- status and support ownership;
- category/severity where known;
- ordered agent/component activity;
- commands/tools and relevant outputs;
- runbook reference/details where applicable;
- safety/refusal evidence;
- technical verification result;
- user confirmation;
- incident documentation information;
- escalation payload / previous attempts;
- bounded demo metrics where useful.

Dev1 owns producing/reporting trustworthy endpoint evidence. Dev2 owns storing and presenting it. Any schema extension should be optional/additive where possible so both lanes can progress independently.

---

# Workload rationale

This split intentionally does not give every developer the same kind of work.

- **Dev1** has the deepest technical/runtime lane because it touches state, execution, orchestration, reliability and test automation.
- **Dev2** has a technically substantial but isolated product lane around the already-existing Service Desk and its data model.
- **Dev3** has a meaningful, highly visible frontend/product lane with hard backend boundaries. The developer's AI assistant will provide stronger operational handholding and must not assume command-line or software-development tooling knowledge.

All three lanes directly contribute to the final 15-minute demo. No lane is merely "documentation" or filler work.

---

# Integration order after the lanes return

The expected integration sequence is:

1. Dev1 runtime/scenario contract is validated.
2. Dev3 employee/Demo Lab experience is integrated against the frozen endpoint APIs.
3. Dev2 Service Desk/Live Operations is integrated against the endpoint ticket payload.
4. Run the complete automated demo rehearsal.
5. Conduct adversarial/wargame rehearsal of the actual 15-minute presentation.
6. Fix only integration/demo blockers and high-value polish.
7. Freeze the final demo commit.
8. Reconcile TDD, screenshots, evidence, and narration to that exact commit.

The detailed per-developer workstream contracts and AI bootstrap prompts are the next project step.
