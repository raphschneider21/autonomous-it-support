# Project Roadmap & Living Work Tracker

## Academic Milestone Overview
- **Deadline**: 30 September 2026 at 23:59
- **Deliverables**: 15-Minute Live PoC Demonstration + Technical Design Document (TDD)
- **Target Standard**: "Exceeded" (10/10 points) on all 10 rubric categories (`docs/grading-and-deliverables.md`)

---

## Milestone 0: Conceptual Foundation & Problem Modeling (Active Phase)
*Goal: 100% alignment across all three developers on problem boundaries, schemas, and user flows before writing production code.*

### `@Dev1` — Core Diagnostic Engine & Safety Boundaries
- [x] Establish Tier 1 vs Tier 2 problem boundaries in [`docs/problem-scope.md`](./problem-scope.md)
- [x] Draft comprehensive command allowlist/blocklist for endpoint execution (Green, Yellow, Red) in [`.agents/rules/safety.md`](../.agents/rules/safety.md)
- [x] Formulate rubric compliance invariants in [`.agents/rules/grading-rubric.md`](../.agents/rules/grading-rubric.md)
- [x] Define the `IExecutor` interface for mocking OS commands during local testing

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
- [x] Define the 15-minute live demonstration script in [`.agents/rules/live-demo-spec.md`](../.agents/rules/live-demo-spec.md)
- [ ] Design the exact JSON contract for the Tier 2 Escalation Ticket payload
- [ ] Wireframe the 3 essential client UI states (Consent screen, Live execution timeline, Verification check)
- [ ] Research lightweight desktop client / web frameworks (Next.js/FastAPI vs lightweight web UI)

---

## Milestone 1: Interface Contracts (`docs/schema.md`)
*Goal: Freeze data contracts so all three developers can build their subsystems independently.*
- [ ] `@All` Review and freeze `RunbookSchema` (YAML/JSON)
- [ ] `@All` Review and freeze `DiagnosticEvent` stream schema (Engine -> UI)
- [ ] `@All` Review and freeze `EscalationTicket` schema (Engine -> ServiceNow/Jira)
- [ ] `@All` Review and freeze `IncidentReport` schema (Markdown generator)
- [ ] `@All` Freeze SQLite schema for incident records, audit trails, and execution metrics

---

## Milestone 2: Prototype Subsystem Implementation
- [x] `@Dev1` Implement `MockExecutor` and `SafetyValidator` with unit test suite
- [ ] `@Dev2` Implement `RunbookParser` and `RunbookMatcher` with benchmark tests
- [ ] `@Dev3` Build prototype client UI with simulated event streaming and ticket submission

---

## Milestone 3: Integrated End-to-End Prototype
- [x] Connect Client UI -> Core Engine -> Runbook Store (exercised via real HTTP + SSE in `tests/test_e2e.py`)
- [x] Execute End-to-End automated test for "Stuck Print Spooler" fixture
- [x] Execute End-to-End automated test for "Unresolvable Escalation" fixture
- [x] Demonstrate Dual-Documentation generation upon fix (resolution report asserted in E2E)
- [x] Demonstrate multi-agent disagreement resolution (Infrastructure vs. Security) — E2E + demo segment 3 scenario in `tests/test_e2e.py`

---

## Milestone 4: Testing Cycles & Efficiency Optimization (Rubric 4 & 6)
*Goal: Gather empirical evidence for TDD Sections 3 and 5 across two distinct testing rounds.*
- [x] **Round 1 Testing (Baseline Functionality & Edge Cases)**:
  - [x] Run 10-incident test suite (`tests/test_suite.json`) covering realistic issues, ambiguous symptoms, and missing telemetry via `tests/test_suite_runner.py`.
  - [x] Test malicious inputs and prompt injection defense (e.g. "Elevate user to admin", "disable the firewall").
  - [x] Log baseline metrics: classification accuracy, latency (ms), tool-call count → `data/benchmarks/round1.json`. Round 1 baseline: 100% accuracy, ~8ms avg latency, ~2.2 avg tool calls.
  - [x] Capture failure logs and screenshots for TDD Section 3 → `docs/tdd-evidence.md` + `docs/tdd-evidence/*.log` (live-captured RED→GREEN pairs).
- [ ] **Optimization & Iteration (Major Changes)**:
  - [x] Add runbook-store caching so repeated incidents skip disk I/O + YAML parse (Round 2)
  - [x] Deduplicate identical diagnostic commands in one pass
  - [ ] Refine agent prompts, model configurations, and tool routing based on Round 1 failures.
  - [ ] Implement caching/early-exit logic to reduce latency and token consumption.
  - [ ] Document rationale and changes with peer/expert citations for TDD Section 4.
- [ ] **Round 2 Testing (Performance & Hardened Guardrails)**:
  - [x] Re-run test suite and measure outcome improvements.
  - [x] Generate comparative Before-vs-After benchmark table for TDD Section 5 → `docs/benchmark-round2.md`.
  - [x] Round 2 result: 100% accuracy, **3.3 ms avg (**-49%)**, 2.22 tool calls.

---

## Milestone 5: TDD Compilation & Live Demo Rehearsal (Rubric 5, 7, 8, 9, 10)
- [ ] **TDD Authoring**:
  - [x] Working draft `docs/tdd.md` (Sections 1-8, evidence-backed; TEAM INPUT markers for peer citations, AI-use disclosure, screenshots)
  - [ ] Complete Sections 1 through 8 adhering to template requirements and continuous evidence logs.
  - [ ] Add AI-use disclosure (Section 7) reflecting on development tools and safety/security controls.
- [ ] **Live Demonstration Dry-Runs**:
  - [ ] Rehearse the 15-minute live demonstration adhering to the cadence in [`.agents/rules/live-demo-spec.md`](../.agents/rules/live-demo-spec.md).
  - [ ] Verify seamless execution of the live incident, under-the-hood traces, human approval modal, prompt injection block, and results summary.
