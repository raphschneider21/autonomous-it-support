# Project Roadmap & Living Work Tracker

## Milestone 0: Conceptual Foundation & Problem Modeling (Active Phase)
*Goal: 100% alignment across all three developers on problem boundaries, schemas, and user flows before writing production code.*

### `@Dev1` — Core Diagnostic Engine & Safety Boundaries
- [x] Establish Tier 1 vs Tier 2 problem boundaries in [`docs/problem-scope.md`](./problem-scope.md)
- [ ] Draft comprehensive command allowlist/blocklist for endpoint execution (Green, Yellow, Red)
- [ ] Research OS execution mechanisms (PowerShell 7 vs Windows PowerShell 5.1 vs bash/sh for cross-platform)
- [ ] Define the `IExecutor` interface for mocking OS commands during local testing

### `@Dev2` — Knowledge Base & Dual-Documentation Architecture
- [x] Draft the initial Dual-Documentation specification in [`docs/documentation-model.md`](./documentation-model.md)
- [ ] Create 3 synthetic real-world Runbook fixtures:
  - `fixtures/runbooks/cisco-vpn-stuck-adapter.yaml`
  - `fixtures/runbooks/windows-print-spooler-crash.yaml`
  - `fixtures/runbooks/legacy-vbscript-missing-drive.yaml`
- [ ] Design the matching algorithm (how the agent matches symptoms to existing runbooks in sub-second time)
- [ ] Draft strategy for ingesting internal legacy enterprise scripts into a vector index (RAG)

### `@Dev3` — Endpoint Client Experience & ITSM Escalation Bridge
- [x] Map out the end-to-end user workflow in [`docs/user-journey.md`](./user-journey.md)
- [ ] Design the exact JSON contract for the Tier 2 Escalation Ticket payload
- [ ] Sketch/wireframe the 3 essential client UI states (Consent screen, Live execution progress, Verification check)
- [ ] Research lightweight desktop client frameworks (Tauri vs Electron vs lightweight web/webview)

---

## Milestone 1: Interface Contracts (`docs/schema.md`)
*Goal: Freeze data contracts so all three developers can build their subsystems independently.*
- [ ] `@All` Review and freeze `RunbookSchema` (YAML/JSON)
- [ ] `@All` Review and freeze `DiagnosticEvent` stream schema (Engine -> UI)
- [ ] `@All` Review and freeze `EscalationTicket` schema (Engine -> ServiceNow/Jira)
- [ ] `@All` Review and freeze `IncidentReport` schema (Markdown generator)

---

## Milestone 2: Prototype Subsystem Implementation
- [ ] `@Dev1` Implement `MockExecutor` and `SafetyValidator` with unit test suite
- [ ] `@Dev2` Implement `RunbookParser` and `RunbookMatcher` with benchmark tests
- [ ] `@Dev3` Build prototype client UI with simulated event streaming and ticket submission

---

## Milestone 3: Integrated End-to-End Prototype
- [ ] Connect Client UI -> Core Engine -> Runbook Store
- [ ] Execute End-to-End automated test for "Stuck Print Spooler" fixture
- [ ] Execute End-to-End automated test for "Unresolvable Escalation" fixture
- [ ] Demonstrate Dual-Documentation generation upon fix
