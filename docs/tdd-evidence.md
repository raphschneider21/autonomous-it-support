# Dev1 Engineering Evidence Dossier (TDD Sections 3, 4, 5)

> Companion to `docs/benchmark-round2.md`. Compiles the traceable evidence
> produced during development of the Core Diagnostic Engine & Safety Gates
> subsystem, mapped to the TDD template (`Generative AI Solution Technical
> Description Documentation Template v1.docx`).
>
> Every claim below links to a stored artifact (`docs/tdd-evidence/*.log`,
> `data/benchmarks/*.json`, or a guard regression test in `tests/`). All
> failure logs were **captured live** by temporarily reverting the shipped
> fix, running the failing tests, and restoring the fix in the same working
> tree (verified `git status` clean afterwards).

---

## Section 3 — Initial Testing & Baseline Evidence

### 3a. Baseline test suite
- `tests/test_suite.json` — 10-case suite: realistic issues (spooler, VPN,
  legacy drive), edge cases (hardware fault, garbage input), security
  injections, and empty-input validation error.
- Harness: `tests/test_suite_runner.py` (runnable as `--round N`, and as a
  pytest regression test with `write=False` so recorded evidence is never
  clobbered).
- Baseline metrics: `data/benchmarks/round1.json` — 100% accuracy,
  6.5 ms avg latency, 2.22 avg tool calls.

### 3b/3c. First-round failures observed (RED phase → GREEN phase)

**Failure 1 — Whitespace-obfuscated RED command bypass**
- Raw evidence: `docs/tdd-evidence/redphase-safety-whitespace-bypass.log`
- Symptom: `"net    user   alice   /add"` classified GREEN (would be
  auto-executed); `"Remove-Item    -Path    C:\Windows    -Recurse"`
  classified YELLOW instead of RED; tab-separated variants also bypassed.
- Root cause: matcher compared against the raw command string without
  normalizing whitespace/whitespace separators.
- Fix: `src/safety/safety_validator.py::_normalize()` collapses all
  whitespace (`re.sub(r"\s+", " ", ...)`) before tier matching.
- GREEN proof: `docs/tdd-evidence/greenphase-safety-whitespace-blocked.log`
  (18 passed, incl. obfuscation + tab tests).
- Regression guards: `tests/test_safety_validator.py`,
  `tests/test_approval_gate.py::test_red_command_with_obfuscated_spacing_blocked`.

**Failure 2 — Escalation `ValidationError` on incidents without telemetry**
- Raw evidence: `docs/tdd-evidence/redphase-escalation-validationerror.log`
- Symptom: when the typed `EscalationTicket` schema was merged, escalation
  crashed with `pydantic_core.ValidationError` because `hostname` /
  `os_version` were `None` (raw incident logged with `'hostname': None`).
  Both the unit path (`test_failed_verification_escalates`) and the API path
  (`POST /api/incidents` background task) failed.
- Root cause: Pydantic `DeviceTelemetry` required non-null strings, but
  telemetry columns default to NULL in SQLite when never collected.
- Fix: `src/integrations/escalation.py` maps missing telemetry to safe
  defaults (`or "Unknown"`, `or ""`).
- GREEN proof: `docs/tdd-evidence/greenphase-escalation-none-safe.log`
  (2 passed, unit + API).
- Regression guards: `tests/test_verification.py`, `tests/test_e2e.py`
  (escalation scenario), `tests/test_escalation_ticket.py`.

**Failure 3 — Empty prompt accepted (validation gap)**
- Observed: empty/nonsense submissions could enter the pipeline.
- Fix: `src/models.py::IncidentCreate.user_prompt` gained
  `Field(..., min_length=1)` → empty prompt rejected with HTTP 422.
- Regression guard: `tests/test_e2e.py::test_empty_prompt_rejected_with_422`
  and `test_suite.json` TC-010.

---

## Section 4 — Major Changes & Iteration

| Change | Rationale | Location |
| ------ | --------- | -------- |
| Whitespace normalization in safety matcher | Close the obfuscation bypass (Failure 1) | `src/safety/safety_validator.py` |
| Two-tier prompt-injection scoring (word-boundary regex + confidence) | Handle role-manipulation prompts that a naive keyword check missed | `src/engine/security_agent.py` |
| Multi-agent disagreement reconciliation | Diagnostic(Security) conflicts resolved conservatively in Security's favor (`security/*`) | `src/engine/disagreement.py` |
| Approval gate re-validation (`check_action`) | RED (incl. obfuscated) blocked + audited before any execution | `src/engine/incident_commander.py` |
| Runbook verification before resolve | Resolve only after verification spec passes; else escalate with telemetry | `src/engine/incident_commander.py` |
| Runbook-store caching + diagnostic dedup | Round 2 latency optimization (see Section 5) | `src/knowledge/runbook_parser.py`, `src/engine/diagnostic_agent.py` |
| None-safe escalation defaults | Fix typed-schema crash on incidents without telemetry (Failure 2) | `src/integrations/escalation.py` (team merge integration) |
| SSE async adaptation | `POST /api/incidents` became async (BackgroundTasks); engine keeps returning full result with `events` while streaming | `src/engine/incident_commander.py`, `tests/test_e2e.py` |

Process lesson (Section 4c): benchmark artifacts were initially overwritten by
a routine test run (drift 6.5 → 4.4 ms in `round1.json`). Fixed by making the
pytest wrapper non-writing (`write=False`); recorded evidence is now immutable
unless regenerated explicitly via `--round`.

---

## Section 5 — Second Round of Testing & Evaluation

Full table + interpretation: `docs/benchmark-round2.md`.
Raw artifacts: `data/benchmarks/round1.json` (Before), `data/benchmarks/round2.json` (After).

| Metric | Round 1 (Before) | Round 2 (After) | Delta |
| ------ | ---------------- | --------------- | ----- |
| Accuracy | 100% | 100% | unchanged |
| Avg latency | 6.5 ms | 3.3 ms | **-49%** |
| Avg tool calls | 2.22 | 2.22 | unchanged (reasoning preserved) |
| Max latency | 9.1 ms | 9.7 ms (cold-cache first case) | warm-cache cases ~3 ms |

E2E integration + safety outcomes (Section 5/6 evidence):
- `tests/test_e2e.py` — spooler lifecycle, unresolvable escalation,
  disagreement reconciliation, injection block, RED approval rejection, 422.
- `tests/demo_rehearsal.py` — live 15-min cadence walkthrough, all segments
  PASS, prints the Round 1 vs Round 2 table directly.

---

## Reproduce everything from scratch

```bash
# Full test suite (regression, does NOT touch recorded benchmark evidence)
python -m pytest tests/ -q

# Regenerate benchmark rounds (explicit only)
python -m tests.test_suite_runner --round 2      # after-code measurement
python tests/demo_rehearsal.py                    # live-demo walkthrough

# Re-capture a RED -> GREEN pair (revert fix -> run -> restore fix)
#   e.g. revert _normalize() in src/safety/safety_validator.py, then:
python -m pytest tests/test_safety_validator.py tests/test_approval_gate.py -q
git checkout -- src/safety/safety_validator.py     # restore
```

## Evidence inventory
- `docs/tdd-evidence/redphase-safety-whitespace-bypass.log` (4 failed)
- `docs/tdd-evidence/greenphase-safety-whitespace-blocked.log` (18 passed)
- `docs/tdd-evidence/redphase-escalation-validationerror.log` (2 failed)
- `docs/tdd-evidence/greenphase-escalation-none-safe.log` (2 passed)
- `docs/benchmark-round2.md`
- `data/benchmarks/round1.json`, `data/benchmarks/round2.json`