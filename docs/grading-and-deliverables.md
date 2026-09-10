# Academic Deliverables & Grading Evidence Map

This repository contains the **Autonomous Enterprise IT Support PoC** for the FHNW Generative AI module.

- **Deadline:** 30 September 2026, 23:59
- **Deliverables:**
  1. 15-minute live Proof-of-Concept demonstration
  2. Technical Design Document (TDD) using the course template

This document maps the course evaluation areas to **current evidence that actually exists**. It is not a claim that every category is automatically worth 10/10; the purpose is to make the final TDD and demo traceable and to avoid unsupported statements.

## 1. Current execution baseline

The graded demo runs on one Mac with:

```text
Employee Support / Incident Engine       :8000
Demo Lab                                 :8000/static/demo.html
Simulated Ubuntu 26.04 endpoint          ubuntu-demo-01
MockExecutor                             stateful simulation
Agent mode                               deterministic PoC
Service Desk / Live Operations           :8001
```

Separate optional model-backed and real-executor paths exist in the repository. The deterministic demo and live-model benchmark evidence must be described separately.

## 2. Rubric-to-evidence matrix

| ID | Assessment area | What the project should demonstrate/document | Current evidence |
| --- | --- | --- | --- |
| **1** | Business case | Quantified, justifiable potential impact with assumptions made explicit | `docs/problem-scope.md` contains the current illustrative time/cost model and labels it as estimated; TDD Section 1 should preserve that distinction |
| **2** | Agents | Functioning multi-agent workflow; named roles/goals; prompt/model/settings rationale | `src/engine/llm.py` contains per-agent system prompts, model choices, max-token settings, adaptive-thinking/effort settings and rationales; deterministic fallback uses the same role architecture for the graded path |
| **3** | Tools | Multiple tools/integrations with technical and business-value explanation | `IExecutor`/MockExecutor, YAML runbooks, FastAPI REST/SSE, SQLite incident/audit storage, Service Desk HTTP integration, report generation and Demo Lab state controls |
| **4** | Efficiency | Measured optimisation balancing correctness, latency and/or cost | `docs/benchmark-round2.md`, `data/benchmarks/round1.json`, `round2.json`; separate live Claude token/cost/latency evidence in `round1-live.json` |
| **5** | Detailing & progress | Decisions, failures, fixes and why changes were made | `docs/tdd-evidence.md`, architectural decisions, commit history, integration/reliability work |
| **6** | Experimentation | Multiple test/adjustment cycles with observed effects | RED→GREEN safety and escalation failures; before/after runbook-cache optimisation; adversarial and scenario testing |
| **7** | Reflections | Lessons, trade-offs, limitations and production implications | TDD Section 6 must synthesize the existing evidence rather than only list features |
| **8** | Business demo | Working end-to-end lifecycle tied to business problem and scaling potential | Scenario A/B lifecycle plus Service Desk handoff; `.agents/rules/live-demo-spec.md` includes the current business-impact narration |
| **9** | Technology demo | Under-the-hood evidence, tool calls, state transitions, agent disagreement/adaptability | Service Desk Live Operations, Demo Lab state transitions, disagreement/reconciliation path, runtime health/mode transparency |
| **10** | Ethics & safety | Relevant risks plus concrete controls and an ongoing evaluation strategy | `.agents/rules/safety.md`, prompt-injection tests, default-deny allowlist, up-front consent, refusal/escalation, auditability, verification + user confirmation |

## 3. Evidence by category

### 3.1 Business case

Current working assumptions are recorded in `docs/problem-scope.md`:

```text
Manual handling assumption:     25 min / repeatable ticket
Automated handling assumption:   1.5 min / successfully automated ticket
Technician cost assumption:      CHF 60/h
Potential capacity released:    23.5 min / CHF 23.50 per safely automated case
```

These are **illustrative assumptions**, not measured customer/company data. The TDD should not describe them as factual industry averages without an external source.

A useful product metric already present in the Service Desk is `false_resolution_rate`: the share of employee-confirmed cases in which technical verification passed but the employee still reported the problem as unresolved.

### 3.2 Agents

The model-backed role configuration is implemented in `src/engine/llm.py`.

| Role | Model | Current rationale in code |
| --- | --- | --- |
| Triage Agent | Claude Haiku 4.5 | inexpensive/fast structured classification |
| Diagnostic Agent | Claude Opus 5 | evidence-heavy root-cause reasoning |
| Security Agent | Claude Haiku 4.5 | focused manipulation/security-pattern detection |
| Incident Commander | Claude Sonnet 5 | reconciliation over structured specialist assessments |

The code documents exact max-token and adaptive-thinking/effort settings. `model_table()` can render these values directly for documentation.

Important distinction for the final report:

- **architecture exists and has been evaluated with live Claude calls**;
- **graded A/B/C demo runs deterministic fallbacks for reliability**.

Do not write that the deterministic demo generated its reasoning through Claude.

### 3.3 Tools

The current PoC includes multiple functioning tool boundaries:

- `IExecutor` abstraction;
- stateful `MockExecutor`;
- strict command safety validator;
- YAML operational runbook loader/matcher;
- SQLite incident and audit persistence;
- Server-Sent Events for live progress;
- Service Desk HTTP ticket reporting;
- separate Service Desk SQLite persistence;
- incident-report generation;
- Demo Lab endpoint-state API;
- one-click Mac launcher and preflight/rehearsal tooling.

The TDD should explain **why each tool exists**, not merely enumerate libraries.

### 3.4 Efficiency and measured evaluation

#### Deterministic code optimisation

`docs/benchmark-round2.md` records:

| Metric | Round 1 | Round 2 | Delta |
| --- | ---: | ---: | --- |
| Accuracy | 100% | 100% | unchanged |
| Avg latency | 6.5 ms | 3.3 ms | ~49% lower |
| Avg tool calls | 2.22 | 2.22 | unchanged |

The implemented change caches parsed runbooks and deduplicates identical diagnostic commands.

#### Live Claude evaluation

`data/benchmarks/round1-live.json` records a distinct 10-case live-model run:

```text
10/10 cases passed
p95 latency: 14.17 s
average API cost: USD 0.01223 / incident
```

The artifact also retains per-case token usage, model calls and cost. Do **not** compare the live-model seconds directly with the deterministic millisecond benchmark as if they measured the same workload/mode.

### 3.5–3.7 Progress, experimentation and reflection

The strongest current evidence is not a perfect green test history; it is the documented failure/fix process.

Examples in `docs/tdd-evidence.md` include:

- whitespace-obfuscated dangerous commands bypassed an earlier matcher → normalization + regression coverage;
- an escalation schema failed on missing telemetry → None-safe mapping + unit/API regression coverage;
- empty input entered the pipeline → API validation;
- repeated runbook loading created avoidable latency → caching;
- benchmark files were accidentally vulnerable to test-run drift → evidence generation was separated from regression execution.

The final TDD should use these examples to explain how the design changed and what the team learned.

### 3.8 Business demonstration

The live demo is structured around three outcomes:

```text
A. It fixes something.
B. It knows when to hand over.
C. It refuses something.
```

Scenario B is particularly useful for business value because it demonstrates that an unsuccessful employee outcome still produces a prepared Human-L2 handoff rather than wasting the automated work.

### 3.9 Technology demonstration

Primary evidence surfaces:

- Demo Lab for controlled state changes;
- Employee Support for user-facing workflow;
- Live Operations for structured technical trace;
- Service Desk for lifecycle/ownership/documentation;
- `/api/health` for executor/agent-mode transparency.

The presentation should show actual evidence and state transitions rather than invented internal thought/confidence.

### 3.10 Ethics and safety

Current implemented controls include:

- one **up-front informed troubleshooting consent**;
- Green/Yellow/Red/unknown policy classification;
- strict default-deny allowlist;
- argument validation rather than binary-only validation;
- no `shell=True` command path;
- direct prompt-injection detection;
- fenced untrusted tool output for indirect-injection resistance;
- refusal + audit + escalation for prohibited requests;
- technical post-remediation verification;
- employee confirmation before successful final closure.

The course rubric asks for ethical evaluation/standards to be discussed. The final TDD should reference only standards the team has actually reviewed and can explain; do not insert a standard name purely for decoration.

## 4. Current authoritative documentation

| File | Purpose |
| --- | --- |
| `docs/final-demo-plan.md` | Accepted product/demo baseline |
| `README.md` | Current repository overview and launch path |
| `docs/problem-scope.md` | Business problem, assumptions and operational boundary |
| `docs/user-journey.md` | Current employee/L1/L2 journey |
| `docs/schema.md` | Current interfaces/data contracts |
| `docs/tdd.md` | Working TDD content |
| `docs/tdd-evidence.md` | Testing/iteration evidence dossier |
| `docs/benchmark-round2.md` | Deterministic optimisation comparison |
| `data/benchmarks/round1-live.json` | Recorded live Claude evaluation |
| `.agents/rules/live-demo-spec.md` | Current 15-minute demo choreography |
| `.agents/rules/safety.md` | Current consent and execution policy |
| `scripts/demo/README.md` | Launch, preflight and rehearsal procedures |

Historical workstream/roadmap documents can be useful for process history but should not override the current baseline.

## 5. Human-only evidence still required

The repository cannot truthfully infer these items and the team must supply them before final submission if they are required by the course template:

- actual peer/lecturer/expert feedback and dates;
- final team-member contribution statements;
- exact development AI tools used by each team member;
- screenshots captured from the final demonstration;
- any organisation-specific business data or interviews;
- final references/citations selected by the team.

These items should remain explicitly marked as team input rather than fabricated.
