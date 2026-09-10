---
trigger: always_on
description: FHNW grading criteria mapped to the current Autonomous IT Support PoC and evidence requirements.
---

# FHNW Generative AI Project — Grading Criteria & Project Evidence Rules

This document preserves the project's working transcription of the ten course evaluation areas and maps them to the **current implementation/evidence**. It must not be used to invent evidence or silently change the product to match an outdated internal assumption.

Where the course rubric describes an outcome (for example human oversight or ethical evaluation), the current project implementation may satisfy that outcome differently from an earlier prototype design. The current product baseline is defined by `docs/final-demo-plan.md`; the current safety semantics are defined by `.agents/rules/safety.md`.

**Submission deadline:** 30 September 2026, 23:59  
**Deliverables:**

1. 15-minute live Proof-of-Concept demonstration.
2. Technical Design Document using the course template.

---

## 1. Working rubric mapping

| ID | Category | Sub-category | Aspect | Working "Exceeded" standard from course mapping | Current project evidence / documentation target |
| --- | --- | --- | --- | --- | --- |
| **1** | Documentation | Business | Business Case | Quantifies potential business impacts such as ROI, cost savings, time efficiency, ethical issues, or error reduction with justifiable estimates specific to the use case | `docs/problem-scope.md` + TDD Section 1; clearly label assumptions vs measurements |
| **2** | Documentation | Technology | Agents | Functioning multi-agent workflow that improves UX/performance without unjustified speed/cost trade-offs; agents are named, have explicit goals, use prompt-engineering practices, have argued model selection, and documented settings | `src/engine/llm.py` + TDD Section 2; explain deterministic graded path separately from live Claude implementation/evaluation |
| **3** | Documentation | Technology | Tools | Multiple tools integrated with detailed analysis of how each enhances functionality and business value | Executor boundary, safety validator, runbooks, SQLite, FastAPI/SSE, Service Desk HTTP integration, report generation, Demo Lab |
| **4** | Documentation | Technology | Efficiency | Comprehensive optimisation strategies balancing speed, accuracy and cost with measured outcomes | Deterministic before/after benchmark (`round1.json` vs `round2.json`) + separate live Claude token/cost/latency evidence (`round1-live.json`); never merge unlike modes into a misleading comparison |
| **5** | Documentation | Implementation | Detailing & Progress | Reflects on decisions, what worked, what failed, and why | `docs/tdd-evidence.md`, architectural decisions, integration changes, TDD Section 4 |
| **6** | Documentation | Implementation | Experimentation & Adjustment | Multiple cycles of experimentation and adjustment with insights into impact | RED→GREEN safety/escalation evidence, deterministic optimisation round, adversarial and end-to-end rehearsal tests |
| **7** | Documentation | Implementation | Reflections / Insights | Detailed reflections on implementation, challenges and lessons learned | TDD Section 6 must synthesise trade-offs and limitations rather than only list features |
| **8** | Demonstration | Business | Business Case Application | Relates the working solution to the business problem, metrics, applicability and scaling potential | Scenario A/B lifecycle + Service Desk handoff + explicit estimated business-impact model in `.agents/rules/live-demo-spec.md` |
| **9** | Demonstration | Technology | Technology Deployment | Compelling technical dive showing adaptability to users and under the hood | Employee Support, Demo Lab state transition, Live Operations audit/tool trace, disagreement/reconciliation, current APIs |
| **10** | Demonstration | Ethics | Ethical Considerations & Solutions | Identifies key ethical issues and provides a strategy for ongoing ethical evaluation using appropriate, specific industry standards | Current hard controls + TDD ethical reflection; **[TEAM INPUT/REFERENCES]** add only standards the team actually reviewed and can explain |

---

## 2. Current architectural/runtime invariants

### 2.1 Runtime agents vs coding assistants

- Runtime roles execute inside the application architecture: Incident Commander, Triage Agent, Diagnostic Agent and Security Agent.
- Development assistants such as Codex/Antigravity/opencode are implementation tools and belong in the AI-use disclosure section, not in the runtime architecture.
- The live-model role definitions, prompts and settings are in `src/engine/llm.py`.

### 2.2 Graded execution mode

The graded presentation is intentionally:

```text
Mac-only presentation host
simulated Ubuntu 26.04 endpoint
EXECUTOR=mock
AGENT_MODE=deterministic
```

The repository also contains a real Claude path and a real executor path. Those are optional engineering capabilities/evidence and are not to be represented as the running graded path unless the product owner explicitly changes the baseline and the team revalidates it.

### 2.3 Multi-agent disagreement must have a reason to exist

The value of multiple roles should be demonstrated through different objectives/error costs, not theatrical dialogue.

Current disagreement example:

```text
Diagnostic: no ordinary endpoint/infrastructure fault established
Security: strange prompt may indicate credential-harvesting/security risk
Commander: reconciles evidence and escalates conservatively
```

### 2.4 Human oversight and consent

The **current project implementation** uses one up-front troubleshooting consent before the run starts.

- Green read-only diagnostics run automatically.
- Yellow local/reversible state changes may run only if they match the strict allowlist and remain within that accepted troubleshooting scope.
- Red or unknown/unallowlisted actions never execute and are audited/escalated.
- Employee confirmation after technical verification is a second human gate for **closure**, not a command-by-command approval gate.

Earlier internal documents used a per-command Yellow approval modal. That is no longer the running graded workflow and must not be reintroduced solely because an old document says “approval gate”.

If the original course grading spreadsheet explicitly requires command-by-command approval rather than human consent/oversight in general, that requirement must be verified from the source material before changing the working product.

### 2.5 Prompt injection and execution boundary

The current design uses defence in depth:

- direct malicious/manipulative input detection;
- command/log output fenced as untrusted evidence for model-backed reasoning;
- strict default-deny command allowlist;
- argument-level validation;
- no `shell=True` path;
- audit + Human-L2 escalation for blocked work.

### 2.6 Closure semantics

A successful command is not a successful incident.

Closure requires:

1. fresh technical verification after remediation; and
2. employee confirmation that the real problem is solved.

If verification passes but the employee selects **Still Broken**, the case escalates to Human L2 with prior evidence attached.

---

## 3. Evidence integrity rules

These rules apply to every TDD/demo claim:

1. **Measured vs estimated:** business assumptions must be labelled as assumptions/illustrations unless supported by a cited external/organisation source.
2. **Deterministic vs live model:** do not present deterministic millisecond benchmark data as Claude latency, and do not claim deterministic demo text was generated by Claude.
3. **Runbook provenance:** a pre-existing operational runbook used by the engine is not a newly generated runbook.
4. **No invented thinking/confidence:** UI/demo may show structured decisions/evidence, but should not invent hidden chain-of-thought or unsupported confidence percentages.
5. **Final test counts:** insert exact pass counts only after validating the exact submission commit.
6. **Human-only evidence:** peer/lecturer feedback, screenshots, personal AI-tool disclosures and references stay marked `[TEAM INPUT]` until supplied by the team.
7. **Historical docs:** old workstream/roadmap documents can document process history but do not override current behaviour.

---

## 4. High-value evidence already present

### Business

`docs/problem-scope.md` includes an illustrative model based on explicit assumptions and derived time/cost impact.

### Agents

`src/engine/llm.py` contains:

- model per role;
- max-token settings;
- adaptive-thinking/effort settings where applicable;
- role-specific system prompts;
- model-choice rationales;
- structured JSON output contracts.

### Efficiency

Deterministic code-path benchmark:

```text
Accuracy:       100% → 100%
Avg latency:    6.5 ms → 3.3 ms (~49% lower)
Avg tool calls: 2.22 → 2.22
```

Live Claude evaluation:

```text
10/10 cases passed
p95 latency: 14.17 s
average API cost: USD 0.01223 / incident
```

### Experimentation

`docs/tdd-evidence.md` retains authentic examples of defects, fixes and regression guards rather than reconstructing only successful outcomes.

### Technology demo

Current presentation surfaces can show:

- controlled fault injection;
- shared state transition;
- employee workflow;
- structured specialist/action trace;
- runbook match;
- policy decision;
- verification;
- employee verdict;
- automated-L1 to Human-L2 transition;
- generated incident report and escalation context.

### Ethics/safety

Current controls are documented in `.agents/rules/safety.md` and exercised by the refusal/adversarial tests and canonical Scenario C.

---

## 5. Current documentation priority

For final course preparation, prefer these sources in this order:

1. `docs/final-demo-plan.md`
2. current code/API behaviour
3. `.agents/rules/safety.md`
4. `docs/tdd.md`
5. `docs/tdd-evidence.md`
6. `docs/problem-scope.md`
7. `docs/user-journey.md`
8. `docs/schema.md`
9. `.agents/rules/live-demo-spec.md`
10. historical workstream/roadmap material only for process history
