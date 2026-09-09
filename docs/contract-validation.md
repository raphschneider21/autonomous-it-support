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
- **ADR 13**: no recurring-incident early-exit anywhere in `src/engine/` — every
  incident runs security check → triage → diagnostics → disagreement → match.
  Audit evidence intact.
- **ADR 14**: engine uses `classify_from_mock` + `MockExecutor` only;
  `RealExecutor` and Google Gemini are referenced solely in their own tests /
  `docs/` (no live model calls). Demo stays deterministic.
- **ADR 15**: this pass is the pre-freeze gate; open sign-offs remain for
  Dev2 (RunbookSchema) and Dev3 (DiagnosticEvent + EscalationTicket).

## Result
**1 contract drift fixed** (injection `done` frame), **2 Dev2 fixture data
issues flagged**, 3 doc notes. Full suite: **92 passing** after the fix.