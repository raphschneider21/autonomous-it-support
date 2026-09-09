# Technical Design Document (TDD) — Working Draft

> **Status**: Working draft. Content marked **[TEAM INPUT]** must be completed
> by the human team (facts only they hold) — peer/expert citations, AI-use
> disclosure, and screenshots from the recorded demo. Final export target:
> `Generative AI Solution Technical Description Documentation Template v1.docx`
> (course template). Section numbering below follows that template per
> `.agents/rules/tdd-and-evidence.md`.
>
> Traceable evidence: `docs/tdd-evidence.md`, `docs/benchmark-round2.md`,
> `data/benchmarks/round1.json`, `data/benchmarks/round2.json`,
> `docs/tdd-evidence/*.log`, `tests/` (90 tests).

---

## Section 1 — Business Case

### 1a. Description
An enterprise service desk receives hundreds of repetitive Tier-1 tickets
daily. L1 technicians spend roughly 20–30 minutes per ticket manually
collecting device telemetry, checking services, clearing caches, and writing
handover notes — most of which are the same deterministic fixes on local
workstations. This project builds an autonomous endpoint agent that acts as a
reliable first responder: it safely diagnoses Tier-1 incidents, executes
approved remediations, documents resolutions for both AI and human operators,
and escalates out-of-scope work to Tier 2 (boundaries in `docs/problem-scope.md`).

### 1b. Evidence
- Problem scope & Tier 1/2 boundary: `docs/problem-scope.md`.
- User journey & workflow: `docs/user-journey.md`.
- Live demonstration walkthrough covering intake → debate → approval →
  injection defense → outcomes: `docs/tdd-evidence.md` → `tests/demo_rehearsal.py`.

### 1c. Reflections — quantified impact model
Assumptions are stated explicitly; all figures are engineering estimates for
this PoC context and should be case-tuned before production deployment.

| Factor | Baseline (manual L1) | Automated (this PoC) | Justification |
| ------ | -------------------- | -------------------- | ------------- |
| Handling time per Tier-1 ticket | 20–30 min (mean 25 min) | 30 s – 3 min (mean ~1.5 min) | `docs/problem-scope.md` §2; engine latency measured at ~3–7 ms + human approval time; synthetic full cycle in `tests/demo_rehearsal.py` |
| Technician cost per ticket @ CHF 60/h | ~CHF 25 | ~CHF 1.5 + review time | Baseline labor only; agent runs on the endpoint |
| Throughput (100 tickets/day firm, 8 L1 staff) | ~1.9 tickets/h/tech → ~15/day each | Agent clears repeatable fixes unattended; staff cover exceptions | Same taxonomy scope as `docs/problem-scope.md` §3 |
| Error reduction | Manual commands typed by hand | Safety-gated (Green/Yellow/Red) + audit trail | 100% of RED attempts blocked in test suite; prompt-injection cases `test_suite.json` TC-006/007 |
| ROI illustration | — | ~10 daily repeatable tickets/firm → ~CHF 16k/month/technician reabsorbed | Scale-sensitive; re-runs of same runbook cost ~0 (cached store) |

Ethical considerations are covered in Section 6 / rubric category 10.

---

## Section 2 — Initial Setup

### 2a. Runtime multi-agent architecture (exactly four named agents)
| Agent | Goal | Responsibility |
| ----- | ---- | -------------- |
| **Incident Commander** | Orchestrate; final decision maker | Delegates to specialists, runs the approval gate, reconciles disagreements, verifies remediation, writes reports (`src/engine/incident_commander.py`) |
| **Triage Agent** | Classify quickly | Maps user prompt → category + severity (`src/engine/triage_agent.py`) |
| **Diagnostic Agent** | Gather evidence | Runs read-only (Green) probes via `IExecutor`, verifies runbook output (`src/engine/diagnostic_agent.py`) |
| **Security and Policy Agent** | Enforce safety boundary | Prompt-injection detection + two-tier confidence scoring, Green/Yellow/Red tiering, hard-blocking (`src/engine/security_agent.py`, `src/safety/safety_validator.py`) |

> **[TEAM INPUT]** PoC determinism: current `TriageAgent` uses a mock
> classifier (`classify_from_mock`) for 100% demo reliability (rule: minimal,
> reliable infrastructure, `docs/roadmap.md`). If the graded TDD demands LLM
> per-agent model settings, document the Claude parameters in `src/engine/llm.py`
> here. We will not fabricate settings that the running PoC does not use.

### 2b. Tools & integration
| Tool | Purpose | Evidence |
| ---- | ------- | -------- |
| `IExecutor` / `MockExecutor` | Abstract OS-command boundary; stateful mock for demo reliability | `src/executors/`, `tests/test_executors.py` |
| SQLite (`incidents`, `runbooks`, `audit_log`) | Persistence + full auditability | `src/database.py` |
| Runbook store (YAML) | Knowledge retrieval → plan of record | `src/knowledge/`, `fixtures/runbooks/` |
| SSE stream (`EventStreamStore`) | Live agent trace to client UI | `src/engine/event_stream.py`, `tests/test_e2e.py` |
| Report generator | Dual documentation (AI-executable runbook plan + human markdown report) | `src/documentation/`, `tests/test_approval_gate.py` |

### 2c. Reflection
- Model/tool choices favor **reliability over raw capability** for the demo:
  mocks remove flaky external dependencies; all remediation is real work done
  against a local, deterministic endpoint. Any LLM used only adds
  classification nuance; it never holds the execution authority.

---

## Section 3 — Initial Testing & Improvement Planning

### 3a. First round of testing
Baseline suite `tests/test_suite.json` (10 cases): realistic scenarios
(spooler, VPN, legacy drive), edge cases (hardware fault, garbage input),
security prompt injections, and empty-input validation.
- Round 1 result: 100% accuracy; 6.5 ms avg latency; 2.22 avg tool calls
  (`data/benchmarks/round1.json`).
- Guardrail tests: `tests/test_safety_validator.py`, `tests/test_prompt_injection.py`,
  `tests/test_executors.py`.

### 3b. Evidence (failures captured live)
Authentic RED→GREEN test logs in `docs/tdd-evidence/`:
- **RED** `redphase-safety-whitespace-bypass.log` — obfuscated
  `net    user   alice   /add` and tab-separated variants were tiered GREEN
  (auto-executable) with the naive matcher.
- **GREEN** `greenphase-safety-whitespace-blocked.log` — after
  `_normalize()` whitespace collapsing, all variants block correctly.
- **RED** `redphase-escalation-validationerror.log` — after the typed
  `EscalationTicket` schema merge, escalation crashed with
  `pydantic_core.ValidationError` (`hostname=None`) on incidents without telemetry.
- **GREEN** `greenphase-escalation-none-safe.log` — after None-safe defaults.
- Empty prompt → 422 guard: `tests/test_e2e.py::test_empty_prompt_rejected_with_422`.

### 3c. Insights
- Hiding in plain sight: unsafe commands are not adversarial only to
  security *content* — formatting/whitespace is itself an evasion channel.
- Typed schemas catch real incidents at runtime (the merge-time
  `ValidationError` surfaced in live escalation, not just unit tests).

---

## Section 4 — Major Changes & Iteration
Full change log + rationale: `docs/tdd-evidence.md` §4. Highlights:
1. Whitespace normalization in the safety matcher (closes evasion).
2. Two-tier prompt-injection scoring + word-boundary regex.
3. Multi-agent disagreement reconciliation (Security wins by default).
4. Approval gate re-validates blocked/tiered commands; blocked actions audited.
5. Runbook verification before resolve; escalate with telemetry on failure.
6. **Round 2 performance**: runbook-store caching + diagnostic dedup
   (`docs/benchmark-round2.md`).

> **[TEAM INPUT]** The template requires *in-line attribution* for peer and
> visiting-expert feedback (e.g. "Following peer review on YYYY-MM-DD…").
> Add the actual feedback and dates here; do not fabricate. Record any such
> conversations in the appendices.

---

## Section 5 — Second Testing & Evaluation

### 5a. Second round of testing
Same 10-case suite, emphasis on latency + safety after optimization.

### 5b/5c. Evidence — comparative results
| Metric | Round 1 (Before) | Round 2 (After) | Delta |
| ------ | ---------------- | --------------- | ----- |
| Classification accuracy | 100% | 100% | unchanged |
| Avg latency | 6.5 ms | 3.3 ms | **-49%** |
| Avg tool calls | 2.22 | 2.22 | unchanged |
| RED attempts blocked | 100% | 100% | unchanged |
| Injection attempts blocked | 100% | 100% | unchanged |

Raw: `data/benchmarks/round1.json` / `round2.json`; narrative:
`docs/benchmark-round2.md`. E2E + live demo: `tests/test_e2e.py`,
`tests/demo_rehearsal.py`.

> **[TEAM INPUT]** If the graded rubric requires token/API-cost figures,
> either (a) capture representative Claude trials with real token counts, or (b) argue the
> mock-executor equivalence explicitly in this section.

---

## Section 6 — Conclusion & Reflections

### 6a. Final PoC state
An integrated, typed, auditable pipeline: intake → triage → diagnostics →
agent debate → human approval gate → safe execution → verification → dual
documentation → escalation bridge. 90 regression tests, E2E over the real
HTTP/SSE surface, and a rehearsable 15-minute demonstration.

### 6b. Evidence
`docs/tdd-evidence.md`; `tests/test_e2e.py` (full lifecycle); `tests/demo_rehearsal.py`
(segments 2–5 + benchmark table);
**[TEAM INPUT]** attach final workflow screenshots from the recorded demo.

### 6c. Reflection
- The disagreement-resolution path is the architectural heart that justifies
  "multi-agent" beyond decoration: two specialists can disagree, and a
  commander reconciles by evidence weight with a conservative bias.
- The safety gate is a *hard control*, not a policy statement: tiered
  execution + audit + human consent form a defensible human-in-the-loop claim.
- Lessons learned include preserving evidence immutability (benchmark drift
  bug) and keeping the endpoint mock service-level-real for credible demos.

---

## Section 7 — Disclosure of AI Interactions

- Development was assisted by AI coding tools (opencode and teammates' tools)
  for planning, implementation, test authoring, and documentation drafting.
- Review/validation controls used: continuous test suite (90 passing),
  peer-merge review on all integrations, live-captured failure logs, and
  safety-block assertions.

> **[TEAM INPUT]** List the *specific* tools each developer actually used
> (e.g. "Antigravity IDE", "Codex", "Claude", "opencode") and the exact human
> review process followed. This section must be completed by the team — it
> cannot be fabricated.

---

## Section 8 — References
**[TEAM INPUT]** Complete with the course template reference, official edge
SDK/model docs used, and any peer/expert feedback records (Section 4). Note:
standard SDK docs and company operational details do not require citation.

---

## How to finish this draft (checklist)
- [ ] Export to the course DOCX template; align section numbering/headers.
- [ ] **[TEAM INPUT]** Fill Section 4 peer/expert attribution with real dates.
- [ ] **[TEAM INPUT]** Fill Section 7 with real tools + human review process.
- [ ] **[TEAM INPUT]** Attach screenshots from the recorded demo (Sections 1, 2, 3, 5, 6).
- [ ] **[TEAM INPUT]** Decide token/cost evidence strategy (Section 2/5).
- [ ] Rehearse `python tests/demo_rehearsal.py` and record the final demo.