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

## 1. RunbookSchema (YAML) — `fixtures/runbooks/*.yaml`

Loaded by `src/knowledge/runbook_parser.py`; matched by `match_runbook`.
Status: **implemented** (3 fixtures). Sign-off: `@Dev2` **[TEAM INPUT]**.

| Field | Type | Required | Notes |
| ----- | ---- | -------- | ----- |
| `schema_version` | string | yes | `"1.0"` (reserved for future migrations) |
| `runbook_id` | string | yes | Unique, `RB-<DOMAIN>-<NNN>` |
| `title` | string | yes | Human label shown in traces |
| `target_os` | string | yes | Text (windows/linux) — informational |
| `tags` | list[string] | yes | Match keywords (`printer`, `spooler`, …) — contributes +3 score each |
| `trigger_signatures.symptoms` | list[string] | yes | Word-overlap matching against the user prompt |
| `trigger_signatures.error_codes` | list[string] | optional | Exact match on error codes — contributes +10 score each |
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

Reserved invariant: a runbook with **zero** `remediation_steps` is invalid.

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
- [ ] RunbookSchema: `@Dev2` sign-off (fields above match the 3 fixtures).
- [ ] DiagnosticEvent: `@Dev3` UI sign-off on `event`/`done` frame payloads.
- [ ] EscalationTicket: confirm ServiceNow/Jira adapter fields with course staff.
- [ ] `docs/user-journey.md` cross-check for any drift.
- [ ] Audit `action_type` enum freeze (add any future values via version bump).