# Contract & ADR Validation Pass — 2026-09-09

Performed by Dev1 as the Milestone-1 freeze checkpoint. Validates all
implemented artifacts against `docs/schema.md` and decisions 12-15 in
`docs/architectural-decisions.md`.

## 1. RunbookSchema (YAML fixtures) — Dev2 lane

| Check | Result |
| ----- | ------ |
| `schema_version` / `runbook_id` / `title` present | PASS (all 3) |
| `runbook_id` format `RB-<DOMAIN>-<NNN>` | PASS (`RB-PRINT-001`, `RB-VPN-001`, `RB-LEGACY-001`) |
| `trigger_signatures.symptoms` / `error_codes` / `process_names` | PASS |
| `remediation_steps` step objects (`step`/`description`/`command`/`elevation_required`) | PASS |
| `verification` + `rollback_plan` | PASS |
| Non-zero remediation steps invariant | PASS |
| **`target_os` matches command payload** | **FAIL** — all 3 declare `"linux"` yet contain Windows/PowerShell/DOS commands (`Stop-Service`, `ipconfig`, `net use`, `wscript.exe`, `\\\\fileserver`). **Drift #1** |
| Internal consistency (spooler runbook) | **FAIL** — mixes PowerShell (`Get-Service -Name spooler`) with Linux path `/var/spool/cups/*`. **Drift #2** |

> Action: flag to @Dev2; both are informational fields (matching is unaffected)
> but corrupt the demo narrative and future real execution targeting. No code
> change made (fixtures out of Dev1's lane).

**RESOLVED by @Dev2 — 2026-09-09.**

- **Drift #1** — all three fixtures now declare `target_os: "windows_11"`.
- **Drift #2** — the spooler runbook's step 2 now uses the canonical Windows
  path `$env:SystemRoot\System32\spool\PRINTERS\*` (matching
  `docs/documentation-model.md` §2 and `docs/problem-scope.md`), and the
  matching key in `fixtures/mock_outputs.json` moved with it. The step stays
  Yellow-tier (approval-gated) and is not Red.
- **Regression guard**: `tests/test_runbook_store_consistency.py` now asserts
  across *every* store that commands match the declared `target_os` and that no
  single command mixes dialects. Both drifts fail that test if reintroduced.
- **Additional defect found while adding the guard**: nine runbook commands had
  no mock fixture at all and silently returned `[MOCK] No fixture for: ...`.
  The most serious was `Test-NetConnection -ComputerName google.com` — the only
  existing key carried an extra `-InformationLevel Detailed` suffix, so
  **RB-VPN-001's verification never matched and the VPN scenario always
  escalated instead of resolving**. All nine are now covered, and
  `test_every_runbook_command_has_a_mock_fixture` prevents a recurrence.

## 2. DiagnosticEvent SSE contract (engine → UI) — PASS

- Endpoint `GET /api/incidents/{id}/events` emits `event: event` and a single
  terminal `event: done` (`src/main.py:36`).
- Approval-gate `event` frame carries `awaiting: true` + `command`
  (`incident_commander.py:111`).
- Client consumes `addEventListener("event")` / `("done")` and renders
  `pending_command` in the modal (`src/client/app.js:31-64`).
- `done` payload carries `status`/`events`/`runbook_id`/`metrics` in every
  branch, plus `report_path` when resolved and `escalation_ticket` when
  escalated.
- **Drift fixed this pass**: the prompt-injection branch returned `done`
  without `escalation_ticket` (§2b requires it whenever status is escalated).
  Now generates + audits the ticket (`incident_commander.py`, injection branch);
  regression guarded in `tests/test_e2e.py::test_prompt_injection_blocked_through_api`.

## 3. EscalationTicket — PASS
Typed in `src/models.py`, produced None-safe in `src/integrations/escalation.py`
(missing telemetry → `"Unknown"`). Verified across the no-runbook,
verification-failed, and injection escalation paths.

## 4. IncidentReport markdown — PASS
`report_generator.py` output matches §4 structure; paths land in
`data/reports/{incident_id}.md`.

## 5. SQLite schema — PASS
`src/database.py` tables (`incidents`, `runbooks`, `audit_log`) match §5a-c
column-for-column, including the `metrics`-as-`audit_log` row convention
(`action_type='metrics'`, output JSON `{status, latency_ms, tool_calls}` seeded
by `incident_commander.py::_log_metrics`). `seed_runbooks_db()` syncs the YAML
store into `runbooks` at startup (ADR 12 → Milestone store parity).

## 6. ADR conformance sweep (Decisions 12-15) — PASS (2 notes)

- **ADR 12**: mtime-invalidated runbook cache present; diagnostic dedup present.
  Benchmark invariant holds — `write=False` never *overwrites* an existing
  `data/benchmarks/round*.json` (`test_suite_runner.py:115`).
  - Note 1: when the artifact is *absent*, `write=False` still bootstraps it.
    Matches intent (fill-on-first-run) but the docstring says "without touching
    the artifacts on disk" — worth a docstring tighten.
  - Note 2: `data/` is gitignored, so benchmark JSONs are not in version
    control; a fresh clone regenerates them. TDD tables are preserved in the
    committed `docs/benchmark-round2.md`.
    **Addressed by @Dev2**: `.gitignore` narrowed to `data/*` with an exception
    for `data/benchmarks/*.json`, so the artifacts the TDD cites by path are
    now tracked. The incident DB and generated reports stay ignored.
- **ADR 13**: no recurring-incident early-exit anywhere in `src/engine/` — every
  incident runs security check → triage → diagnostics → disagreement → match.
  Audit evidence intact.
- **ADR 14**: engine uses `classify_from_mock` + `MockExecutor` only;
  `RealExecutor` and Google Gemini are referenced solely in their own tests /
  `docs/` (no live model calls). Demo stays deterministic.
- **ADR 15**: this pass is the pre-freeze gate; open sign-offs remain for
  Dev2 (RunbookSchema) and Dev3 (DiagnosticEvent + EscalationTicket).
  **Update**: @Dev2 signed off RunbookSchema at **v1.1** (`docs/schema.md` §1);
  `parameters`, `environment` and `source_case` were added additively and v1.0
  fixtures still parse. Only Dev3's sign-off remains.

## Result
**1 contract drift fixed** (injection `done` frame), **2 Dev2 fixture data
issues flagged**, 3 doc notes. Full suite: **92 passing** after the fix.

---

## Post-merge integration check — 2026-09-09 (@Dev2)

Ran after PR #1 (Ubuntu 26.04 knowledge base) merged into the engine work above.

| Check | Result |
| ----- | ------ |
| Full suite on the merged tree | **PASS** — 307 tests, no regressions in either lane |
| Engine ↔ knowledge layer (`match_runbook`, `load_all_runbooks`, `seed_runbooks_db`) | **PASS** — signatures unchanged; new `store` argument is optional |
| Prompt-injection `done` frame (Dev1's fix) under the Ubuntu store | **PASS** — escalation ticket present |
| Full incident lifecycle on the Ubuntu store | **PASS** — retrieval → approval gate → remediation → verification → report |
| Dev2 fixture drifts #1 and #2 | **FIXED** (above) |
| Runbook commands without a mock fixture | **FIXED** — 9 gaps closed, incl. the RB-VPN-001 verification failure |
| `runbook_id` collisions across stores | **PASS** — asserted by test |
| **Store switch leaves stale runbooks in the DB** | **FIXED** — see below |
| **Escalation ticket title null-safety (schema.md §3)** | **FIXED** — see below |

**Store-switch defect.** `seed_runbooks_db()` writes the active store into the
`runbooks` table, but the database persists across restarts, so rows seeded by
a *previous* store survived. Starting with `RUNBOOK_STORE=ubuntu-26.04`
returned **33** runbooks from `GET /api/runbooks` — the 30 Ubuntu ones plus 3
stale Windows entries the engine could never match. This only bites on the
Milestone 6 cutover, which is exactly when it would have been confusing.

Fixed with `database.prune_runbooks_not_in()`, called from
`seed_runbooks_db()`. Rows still referenced by an incident are **kept**:
`incidents.runbook_id` is a foreign key into this table and a resolved
incident's report cites the runbook that fixed it, so pruning those would
sever the audit trail that ADR 13 treats as inviolable. Both behaviours are
asserted in `tests/test_runbook_store_consistency.py`.

**Escalation ticket title was not null-safe.** `schema.md` §3 guarantees every
`str` field on an `EscalationTicket` is non-null, with missing telemetry mapping
to `"Unknown"`. Exercising Dev1's new prompt-injection escalation path produced:

```
ticket_title: "Escalation: None issue on None"
```

The injection branch escalates *before* triage runs, so `category` and
`hostname` are present-but-`None` on the incident row. `ticket_title` used
`incident.get('category', 'Unknown')`, and `.get(key, default)` only falls back
when the key is **absent** — not when its value is `None`. Every other field in
`generate_escalation_ticket` already used `or "Unknown"` for exactly this
reason; the title was the one that did not. Fixed, with a regression test in
`tests/test_escalation_ticket.py`.

*Note for the owning developer*: `src/integrations/` is the ITSM bridge lane —
this one-line fix is included here because the defect only surfaces on the
escalation path added in this milestone, but please review.
