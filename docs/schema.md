# Interface Contract Freeze — `docs/schema.md`

> **Status**: Draft v0.1 — pending team sign-off (Milestone 1, `@All`).
> Purpose: freeze the data contracts so the engine, runbook store, client UI,
> and escalation bridge can be built independently. Where a schema is already
> implemented, this document is the **source of truth** matching the code;
> where it is a proposal, the freezetrack marker is `[PROPOSED]`.

## Governance
- The schemas below are frozen once all three developers sign off.
- Any post-freeze change = version bump + a `docs/architectural-decisions.md`
  entry with impact analysis; it must not silently diverge from the code.
- Schema validation is enforced in code via Pydantic models (`src/models.py`).

---

## 1. RunbookSchema (YAML) — v1.1

Loaded by `src/knowledge/runbook_parser.py`; matched by `match_runbook`.
Status: **implemented and frozen at v1.1**. Sign-off: `@Dev2` **SIGNED**
(2026-09-09) — fields below match all 33 shipped runbooks and are enforced by
`tests/test_ubuntu_knowledge_base.py`.

### Stores

The knowledge base is split into **stores** so several endpoint platforms can
coexist without polluting each other's retrieval results:

| Store | Directory | Contents |
| ----- | --------- | -------- |
| `default` | `fixtures/runbooks/` | 3 Windows fixtures (existing engine + live demo) |
| `ubuntu-26.04` | `fixtures/runbooks/ubuntu-26.04/` | 30 Ubuntu 26.04 LTS VM runbooks |

`load_all_runbooks()` and `match_runbook()` take an optional `store`; with no
argument they read `$RUNBOOK_STORE`, defaulting to `default`. Store directories
are **not** recursed into, so the two spaces stay disjoint (asserted by
`tests/test_runbook_cache.py`).

### v1.0 -> v1.1 changes

| Field | Change | Reason |
| ----- | ------ | ------ |
| `schema_version` | `"1.0"` -> `"1.1"` | Two optional additive fields below |
| `parameters` | **new**, optional | One runbook covers a family of incidents (which sink, which connector, which block device) instead of hard-coding one machine's values |
| `environment` | **new**, optional | `vm-safe` \| `physical-only` — declares whether the runbook is exercisable on a VM endpoint |
| `source_case` | **new**, optional | Back-reference to the training dataset case (`UB-014`) for traceability |

Backward compatible: all three are optional and the v1.0 Windows fixtures
still parse unchanged.

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `schema_version` | string | yes | `"1.1"` (v1.0 fixtures still parse) |
| `runbook_id` | string | yes | Unique, `RB-<DOMAIN>-<NNN>` |
| `title` | string | yes | Human label shown in traces |
| `target_os` | string | yes | `windows_11` \| `ubuntu_26_04` — informational |
| `environment` | enum | optional | `vm-safe` \| `physical-only` (v1.1) |
| `source_case` | string | optional | Training-dataset case ID (v1.1) |
| `parameters` | list[{name, description, default}] | optional | `{name}` placeholders in commands, resolved from `default` at load time (v1.1) |
| `tags` | list[string] | yes | Curated match keywords — IDF-weighted at 2.0 |
| `trigger_signatures.symptoms` | list[string] | yes | Natural-language phrasings — IDF-weighted at 3.0, plus a bigram phrase bonus |
| `trigger_signatures.error_codes` | list[string] | optional | Quoted error strings — +6.0 each on substring match |
| `trigger_signatures.process_names` | list[string] | optional | Reserved for process-based triggers |
| `pre_checks` | list[{command, expected_output_regex}] | optional | Read-only preconditions (Green only) |
| `remediation_steps` | list of steps | yes | See step schema below |
| `verification` | list[{command, expected_output_regex}] | optional | Must all pass to resolve |
| `rollback_plan` | list[{command}] | optional | Mirrors `remediation_steps` for reversal |

**Step object** (`remediation_steps[]`):
| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `step` | int | yes | 1-based order |
| `description` | string | yes | Shown in the approval modal |
| `command` | string | yes | Exact command executed against the endpoint |
| `elevation_required` | bool | optional | Maps to Yellow tier (requires approval) |
| `timeout_seconds` | int | optional | Informational |

### Enforced invariants

All asserted by `tests/test_ubuntu_knowledge_base.py`:

- A runbook with **zero** `remediation_steps` is invalid.
- `runbook_id` is unique and matches its filename.
- No command in any section may be **Red** tier.
- Every remediation step is either **Yellow** (approval-gated) or provably
  read-only — a step that changes the endpoint can never be auto-executed.
- `pre_checks` and `verification` commands must be **Green** (read-only):
  verification may never itself change state.
- No `{placeholder}` may survive into a command handed to an executor.
- No command may use a subsystem removed in Ubuntu 26.04 (`xrandr`,
  `setxkbmap`, `xkill`, `wmctrl`, `pulseaudio -k`).
- Every runbook's `verification` block must pass against the mock endpoint.

### Retrieval contract

`match_runbook(prompt, error_codes=None, store=None)` returns a runbook **or
`None`**. `None` means *escalate* — it is returned when confidence is below
0.35 or the runner-up margin is below 0.08. `explain_match()` returns the same
decision with `reason`, `confidence`, `margin` and the top-3 candidates for the
audit trail. Algorithm and measured accuracy: `docs/runbook-matching.md`.

---

## 2. DiagnosticEvent Stream Schema (Engine → Client UI)

Transport: Server-Sent Events at `GET /api/incidents/{id}/events`
(`src/engine/event_stream.py`, `src/main.py`). Two frame types:

### 2a. `event` frames (streamed live, one per agent message)
```
event: event
data: {
  "agent":   "DiagnosticAgent",          // exactly one of the 4 runtime agents
  "message": "Ran: Get-Service -Name spooler",
  "tier":    "green",                    // green | yellow | red
  "awaiting": true,                      // present only on approval-gate event
  "command": "Stop-Service -Name spooler -Force"  // present when pending approval
}
```

| Field | Type | Required | Rules |
| ----- | ---- | -------- | ----- |
| `agent` | string | yes | One of: `IncidentCommander`, `TriageAgent`, `DiagnosticAgent`, `SecurityAgent` |
| `message` | string | yes | Non-empty, human-readable |
| `tier` | enum | yes | `green` `yellow` `red` |
| `awaiting` | bool | only on approval gate | `true` + `command` set |
| `command` | string | only with `awaiting` | The Yellow-tier command submitted for review |

### 2b. `done` frame (terminal result)
```
event: done
data: {
  "status": "awaiting_approval",         // open|diagnosing|awaiting_approval|resolved|escalated
  "events": [...DiagnosticEvent],        // full replay appended by engine
  "runbook_id": "RB-PRINT-001" | null,
  "pending_command": "Stop-Service -Name spooler -Force",  // when awaiting_approval
  "escalation_ticket": {...EscalationTicket} | null,        // when escalated
  "report_path": "data/reports/INC-....md" | null,          // when resolved
  "metrics": { "status": str, "latency_ms": float, "tool_calls": int }
}
```
Only a single `done` frame terminates the stream. Sign-off: `@Dev3` (UI)
**[TEAM INPUT]**.

---

## 3. EscalationTicket Schema (Engine → ITSM bridge)

Typed in `src/models.py`, produced by `src/integrations/escalation.py`.
Status: **implemented**; referenced by `tests/test_escalation_ticket.py`.

```
EscalationTicket {
  ticket_title:      str            // "Escalation: <category> issue on <hostname>"
  priority:          str = "P3 - Moderate"
  requester:         Requester      { username, email="", department="unknown" }
  device_telemetry:  DeviceTelemetry{ hostname, os_version, uptime_hours=0.0, last_boot_reason="unknown" }
  issue_context:     IssueContext   {
                       user_reported_symptom: str,
                       detected_error_codes:  list[str] = [],
                       attempted_remediations:list[AttemptedRemediation] = [],
                       agent_assessment:      str
                     }
  incident_id:       str = ""
}
AttemptedRemediation { action: str, result: str, verification_outcome: str }
```
Guarantees: all `str` fields are non-null (missing telemetry maps to `"Unknown"`).

---

## 4. IncidentReport Schema (Markdown, dual documentation)

Produced by `src/documentation/report_generator.py`, written to
`data/reports/{incident_id}.md`. Fixed structure:
```
# Incident Resolution Report: <incident_id>
- Timestamp / Host / User / Initial User Prompt

## 1. Root Cause Summary          (resolution_summary)
## 2. Actions Taken by Agent      (audit_log rows: [ts] [TIER] action: `cmd` — output)
## 3. Verification & Outcome      (final status + runbook link)
```

---

## 5. SQLite Schema (`src/database.py`, `data/incidents.db`)

### 5a. `incidents`
| Column | Type | Constraints |
| ------ | ---- | ----------- |
| `id` | TEXT | PK |
| `created_at` | TEXT | NOT NULL (ISO-8601 UTC) |
| `user_prompt` | TEXT | NOT NULL (min length 1 at API layer) |
| `category` | TEXT | NULL |
| `severity` | TEXT | NULL |
| `status` | TEXT | DEFAULT 'open' |
| `hostname` | TEXT | NULL |
| `os_version` | TEXT | NULL |
| `resolution_summary` | TEXT | NULL |
| `runbook_id` | TEXT | FK → `runbooks.id` |

### 5b. `runbooks`
| Column | Type | Constraints |
| ------ | ---- | ----------- |
| `id` | TEXT | PK |
| `title` | TEXT | NOT NULL |
| `target_os` / `tags` / `trigger_signatures` / `pre_checks` / `remediation_steps` / `verification` / `rollback_plan` | TEXT | JSON-encoded, NULL allowed |
| `created_at` | TEXT | NOT NULL |
| `times_executed` | INT | DEFAULT 0 |
| `times_succeeded` | INT | DEFAULT 0 |

### 5c. `audit_log`
| Column | Type | Constraints |
| ------ | ---- | ----------- |
| `id` | INT | PK AUTOINCREMENT |
| `incident_id` | TEXT | NOT NULL, FK → `incidents.id` |
| `timestamp` | TEXT | NOT NULL |
| `agent_name` | TEXT | NOT NULL |
| `action_type` | TEXT | NOT NULL — `input_check`, `classification`, `diagnosis`, `remediation`, `approval`, `blocked`, `disagreement`, `awaiting_approval`, `escalation`, `verification`, `metrics` |
| `safety_tier` | TEXT | NOT NULL — `green`/`yellow`/`red` |
| `command_executed` | TEXT | NULL |
| `output` | TEXT | NULL |
| `user_approved` | INT | DEFAULT 0 (0/1) |

### 5d. `metrics` convention
Execution telemetry is stored as an `audit_log` row with
`action_type='metrics'` and `output = JSON {status, latency_ms, tool_calls}` —
not a separate table.

---

## 6. Open items for freeze
- [x] RunbookSchema: `@Dev2` **signed off** at v1.1 (2026-09-09); invariants
      enforced by `tests/test_ubuntu_knowledge_base.py`.
- [ ] DiagnosticEvent: `@Dev3` UI sign-off on `event`/`done` frame payloads.
- [ ] EscalationTicket: confirm ServiceNow/Jira adapter fields with course staff.
- [ ] `docs/user-journey.md` cross-check for any drift.
- [ ] Audit `action_type` enum freeze (add any future values via version bump).