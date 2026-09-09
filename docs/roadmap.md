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
- [x] Create 3 synthetic real-world Runbook fixtures:
  - `fixtures/runbooks/cisco-vpn-stuck-adapter.yaml`
  - `fixtures/runbooks/windows-print-spooler-crash.yaml`
  - `fixtures/runbooks/legacy-vbscript-missing-drive.yaml`
- [x] **Build the Ubuntu 26.04 LTS VM knowledge base** — 30 runbooks in
  `fixtures/runbooks/ubuntu-26.04/`, one per resolvable case in
  `tests/dataset_ubuntu_easy.json`. Wayland-only / PipeWire-only / uutils-era
  commands (no `xrandr`, `setxkbmap`, `xkill`, `pulseaudio -k`), enforced by test.
- [x] Design the matching algorithm (how the agent matches symptoms to existing runbooks in sub-second time)
      → `docs/runbook-matching.md`. IDF-weighted field scoring + confidence
      floor and runner-up margin. **p95 0.15 ms**, 100% on 36 held-out
      paraphrases, **0 wrong-runbook matches** (vs 69.4% / 11 unsafe for the
      previous word-overlap matcher).
- [x] Draft strategy for ingesting internal legacy enterprise scripts into a vector index (RAG)
      → `docs/rag-ingestion-strategy.md`. Offline ingestion with a mandatory
      human-review gate; retrieved text is evidence for an author, never an
      executed command.

### `@Dev3` — Endpoint Client Experience & ITSM Escalation Bridge
- [x] Map out the end-to-end user workflow in [`docs/user-journey.md`](./user-journey.md)
- [x] Define the 15-minute live demonstration script in [`.agents/rules/live-demo-spec.md`](../.agents/rules/live-demo-spec.md)
- [ ] Design the exact JSON contract for the Tier 2 Escalation Ticket payload
- [ ] Wireframe the 3 essential client UI states (Consent screen, Live execution timeline, Verification check)
- [ ] Research lightweight desktop client / web frameworks (Next.js/FastAPI vs lightweight web UI)

---

## Milestone 1: Interface Contracts (`docs/schema.md`)
*Goal: Freeze data contracts so all three developers can build their subsystems independently.*
- [x] `@All` Draft contract freeze in `docs/schema.md` (v0.1) with per-schema sign-off trackers
- [x] `@All` Review and freeze `RunbookSchema` (YAML/JSON) — **`@Dev2` signed off
      at v1.1** (2026-09-09); `parameters` / `environment` / `source_case` added
      additively, invariants enforced by `tests/test_ubuntu_knowledge_base.py`
- [ ] `@All` Review and freeze `DiagnosticEvent` stream schema (Engine -> UI) — drafted, needs `@Dev3` sign-off
- [x] `@All` Document `EscalationTicket` schema (Engine -> ServiceNow/Jira) — implemented + documented
- [x] `@All` Document `IncidentReport` schema (Markdown generator) — implemented + documented
- [x] `@All` Document SQLite schema for incident records, audit trails, and execution metrics — implemented + documented

---

## Milestone 2: Prototype Subsystem Implementation
- [x] `@Dev1` Implement `MockExecutor` and `SafetyValidator` with unit test suite
- [x] `@Dev2` Implement `RunbookParser` and `RunbookMatcher` with benchmark tests
      — multi-store parser with mtime-invalidated cache + parameter resolution;
      IDF matcher with abstention. Benchmarks:
      `tests/test_runbook_retrieval_benchmark.py` →
      `data/benchmarks/retrieval-round1.json`. 78 knowledge-base tests total.
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
  - [x] Log baseline metrics: classification accuracy, latency (ms), tool-call count → `data/benchmarks/round1.json`. Round 1 baseline: 100% accuracy, 6.5 ms avg latency, 2.22 avg tool calls.
  - [x] Capture failure logs and screenshots for TDD Section 3 → `docs/tdd-evidence.md` + `docs/tdd-evidence/*.log` (live-captured RED→GREEN pairs).
- [ ] **Optimization & Iteration (Major Changes)**:
  - [x] Add runbook-store caching so repeated incidents skip disk I/O + YAML parse (Round 2)
  - [x] Deduplicate identical diagnostic commands in one pass
  - [x] Refine agent prompts, model configurations, and tool routing based on Round 1 failures. — **No failures to fix**: Round 1 accuracy was 100% (0 misclassifications); prompt/tool config documented in ADR Decisions 2 & 14 (Claude per agent, with deterministic fallbacks). **Superseded**: Round 1 measured the deterministic path only, so 100% accuracy says the test set was too easy to detect a change, not that the system is perfect. Re-baseline against the Ubuntu suite with the model in the loop.
  - [x] Implement caching/early-exit logic to reduce latency and token consumption. — Runbook-store cache + diagnostic dedup done (Round 2). Recurring-incident early-exit implemented then **rejected**: would bypass the per-incident audit trail (see ADR 13).
  - [ ] Document rationale and changes with peer/expert citations for TDD Section 4. — Rationale done in `docs/architectural-decisions.md` (ADR 12-14); peer/expert citations `[TEAM INPUT]`.
- [ ] **Round 2 Testing (Performance & Hardened Guardrails)**:
  - [x] Re-run test suite and measure outcome improvements.
  - [x] Generate comparative Before-vs-After benchmark table for TDD Section 5 → `docs/benchmark-round2.md`.
  - [x] Round 2 result: 100% accuracy, **3.3 ms avg (**-49%)**, 2.22 tool calls.

---

## Milestone 6: Ubuntu 26.04 Cutover (opened by `@Dev2`, 2026-09-09)
*The Ubuntu knowledge base is built, benchmarked and safety-checked, but the
engine still runs the Windows store. These are the remaining steps to flip it.*

- [x] `@Dev2` Ubuntu 26.04 runbook store + retrieval + benchmarks + safety tiers
- [ ] `@Dev1` **Review ADR 19** — `src/safety/safety_validator.py` is your file;
      the Ubuntu tier patterns + specificity resolution are isolated in one
      commit and can be dropped independently. Before the change, 45 of 59
      Ubuntu remediation commands auto-executed as Green.
- [ ] `@Dev1` Convert `triage_agent.py` categories (printer/office/legacy →
      network/audio/packages/desktop/input/display/storage/peripherals) and
      `diagnostic_agent.py` commands from PowerShell to Ubuntu 26.04
- [ ] `@Dev3` Confirm the client UI copy has no Windows-specific wording
- [ ] `@All` Flip `RUNBOOK_STORE=ubuntu-26.04` and re-run the E2E + demo suites
- [ ] `@Dev1`/`@Dev3` Write 10 incident prompts each **without reading**
      `fixtures/runbooks/ubuntu-26.04/`, as a blind retrieval test set — the
      current paraphrase set was authored by the same developer who wrote the
      runbooks, so it is a development set, not an unbiased estimate
      (`docs/runbook-matching.md` §5)

---

## Milestone 5: TDD Compilation & Live Demo Rehearsal (Rubric 5, 7, 8, 9, 10)
- [ ] **TDD Authoring**:
  - [x] Working draft `docs/tdd.md` (Sections 1-8, evidence-backed; TEAM INPUT markers for peer citations, AI-use disclosure, screenshots)
  - [ ] Complete Sections 1 through 8 adhering to template requirements and continuous evidence logs.
  - [ ] Add AI-use disclosure (Section 7) reflecting on development tools and safety/security controls.
- [ ] **Live Demonstration Dry-Runs**:
  - [x] Build dry-run gate `tests/test_demo_dryrun.py` (health, runbook store, UI assets, engine segments; verdict READY TO RECORD) + protocol `docs/demo-dryrun.md`
  - [ ] Rehearse the 15-minute live demonstration adhering to the cadence in [`.agents/rules/live-demo-spec.md`](../.agents/rules/live-demo-spec.md).
  - [ ] Verify seamless execution of the live incident, under-the-hood traces, human approval modal, prompt injection block, and results summary (record final take).
