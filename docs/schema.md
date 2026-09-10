# Current Interface and Data Contracts

> **Status:** current PoC reference.  
> The code remains authoritative if a historical document disagrees with this file.

This document describes the interfaces used by the current Mac-only graded demo and its simulated Ubuntu 26.04 endpoint.

## 1. Runtime mode contract

The graded profile is equivalent to:

```text
DEMO_MODE=1
EXECUTOR=mock
AGENT_MODE=deterministic
RUNBOOK_STORE=ubuntu-26.04
MONITORING_ENABLED=1
MONITORING_URL=http://127.0.0.1:8001
ENDPOINT_NAME=ubuntu-demo-01
```

`GET /api/health` exposes the running values so launch/preflight can verify the actual process rather than trusting shell variables.

Representative fields:

```json
{
  "status": "ok",
  "endpoint": "ubuntu-demo-01",
  "demo_mode": true,
  "agent_mode": "deterministic",
  "requested_agent_mode": "deterministic",
  "external_model_enabled": false,
  "runbook_store": "ubuntu-26.04",
  "monitoring_url": "http://127.0.0.1:8001",
  "monitoring_enabled": true,
  "monitoring_reachable": true
}
```

Executor-description fields are also included and identify whether execution is simulated or can affect the current machine.

## 2. Employee / Incident Engine API — port 8000

### `POST /api/incidents`

Request:

```json
{
  "user_prompt": "My printer isn't printing anything."
}
```

Response:

```json
{
  "incident_id": "INC-XXXXXXXX",
  "status": "diagnosing"
}
```

The incident then runs as a background task.

### `GET /api/incidents/{incident_id}/events`

Transport: Server-Sent Events.

Event frames have the shape:

```text
event: event
data: { ...structured event payload... }
```

When the incident engine completes its technical processing, the stream emits one terminal frame:

```text
event: done
data: { ...result payload... }
```

The exact event payload can contain agent/component name, human-readable message, safety tier, command/output or lifecycle information depending on the event type. Consumers should tolerate additive fields.

There is **no current per-command approval event requirement** in the graded flow. Historical `awaiting_approval` fields/status values can remain in compatibility models, but the current user journey uses one up-front consent before the incident begins.

### `GET /api/incidents/{incident_id}`

Response:

```json
{
  "incident": { "...": "persisted incident record" },
  "audit_log": [
    { "...": "ordered audit entry" }
  ]
}
```

This is the durable evidence view for the endpoint process.

### `POST /api/incidents/{incident_id}/confirm`

Request:

```json
{
  "solved": true
}
```

or:

```json
{
  "solved": false
}
```

Semantics:

- `true` after a technically resolved incident → `closed`, `user_confirmed=solved`;
- `false` after a technically resolved incident → `escalated`, `user_confirmed=still_broken`, with Human-L2 escalation information;
- confirmation on an incident that is not awaiting the employee verdict → HTTP 409.

Representative response:

```json
{
  "incident_id": "INC-XXXXXXXX",
  "status": "closed",
  "user_confirmed": "solved",
  "reported_to_service_desk": true,
  "escalation_ticket": null
}
```

## 3. Demo Lab API

The Demo Lab and `MockExecutor` share one in-memory simulated endpoint state.

### `GET /api/demo/state`

Representative healthy state:

```json
{
  "endpoint": "ubuntu-demo-01",
  "mode": "simulated",
  "available_faults": [
    {
      "id": "cups_stopped",
      "label": "CUPS printing service stopped",
      "category": "printing"
    }
  ],
  "active_faults": [],
  "services": {
    "cups": "active"
  },
  "print_queue": "empty"
}
```

### `POST /api/demo/faults/{fault_id}`

Injects an approved deterministic fault and returns the complete updated state.

Unknown fault IDs return HTTP 404 without mutating the existing state.

### `POST /api/demo/reset`

Restores the simulated endpoint to its known healthy baseline and returns the complete state. Reset is intended to be idempotent.

## 4. Runbook contract

The graded store is:

```text
fixtures/runbooks/ubuntu-26.04/
```

The hero runbook is `RB-CUPS-001`.

Runbook shape:

| Field | Type | Purpose |
| --- | --- | --- |
| `schema_version` | string | Runbook schema revision |
| `runbook_id` | string | Stable identifier |
| `title` | string | Human-readable label |
| `target_os` | string | Intended endpoint platform |
| `tags` | list[string] | Retrieval terms |
| `trigger_signatures` | object | Symptoms/error signatures used for matching |
| `pre_checks` | list[object] | Read-only diagnostic conditions |
| `remediation_steps` | list[object] | Ordered permitted remediation plan |
| `verification` | list[object] | Fresh post-remediation checks |
| `rollback_plan` | list[object] | Reversal guidance where supplied |
| `parameters` | optional list | Controlled placeholder definitions |
| `environment` | optional string | Environment applicability metadata |
| `source_case` | optional string | Evaluation/training traceability metadata |

A remediation-step object includes at least:

```json
{
  "step": 1,
  "description": "...",
  "command": "...",
  "elevation_required": true,
  "timeout_seconds": 10
}
```

`elevation_required`/Yellow classification does **not** imply a current per-command approval modal. In the graded profile, a state-altering command must still match the safety allowlist and then executes only inside the already accepted up-front troubleshooting scope.

Runbook invariants include:

- at least one remediation step;
- unique runbook ID;
- no Red/forbidden command in a valid operational runbook;
- pre-checks and verification remain read-only;
- runtime placeholders must be resolved and revalidated before execution;
- verification must evaluate fresh state rather than assuming command success.

## 5. Safety/executor contract

All OS-style commands pass through `IExecutor`; agent code should not bypass the executor abstraction.

The current graded policy is:

```text
Green   read-only                  allowed automatically
Yellow  local + reversible + allowlisted
                                      allowed inside up-front consent
Red     forbidden/unsafe             blocked
Unknown not explicitly allowlisted   blocked
```

`RealExecutor` exists as an optional engineering path. The graded demo uses `MockExecutor`, which must not change the Mac host.

## 6. Service Desk ingestion contract — port 8001

Endpoint snapshots are sent to:

```text
POST /api/tickets
```

Ticket payload fields currently accepted include:

| Field | Type | Notes |
| --- | --- | --- |
| `incident_id` | string | required, idempotency key |
| `hostname` | optional string | simulated endpoint name |
| `title` | optional string | ticket/display title |
| `status` | string | lifecycle status |
| `category` | optional string | incident class |
| `severity` | optional string | severity |
| `user_prompt` | optional string | original employee report |
| `runbook_id` | optional string | matched operational runbook |
| `resolution` | optional string | summary |
| `agent_source` | optional string | deterministic/Claude/fallback evidence |
| `latency_ms` | optional float | measured engine latency when available |
| `tool_calls` | optional int | measured tool-call count |
| `tokens_in` / `tokens_out` | int | model usage when available |
| `actions` | list[object] | chronological audit/action evidence |
| `errors` | list[object] | refusal/failure subset |
| `escalation` | optional object | Human-L2 escalation payload |
| `user_confirmed` | optional string | `solved` / `still_broken` |
| `incident_report` | optional string | human-readable report content |
| `runbook` | optional object | runbook summary/documentation payload |

Consumers should remain backward-compatible with early lifecycle snapshots where most optional fields are null/empty.

Service Desk maps a technically `resolved` endpoint state to an open ticket until employee confirmation is known. Final employee outcomes become `closed` or `escalated`.

## 7. Service Desk read APIs

```text
GET /api/health
GET /api/tickets
GET /api/tickets/{incident_id}
GET /api/stats
```

The Service Desk persists tickets in a separate SQLite database. Repeated snapshots for the same `incident_id` update the existing ticket rather than creating duplicates.

The database migration path for optional documentation fields is additive so an existing `tickets.db` created before those columns existed can still be opened safely.

## 8. Incident report contract

The human-readable incident report is generated from the actual incident execution evidence. It should not be confused with the operational runbook.

Conceptual distinction:

```text
Runbook
= pre-existing machine-readable operational knowledge used by the system

Incident report
= human-readable record generated from this specific incident execution
```

Do not claim that the runtime generated a new runbook if it used `RB-CUPS-001` or another pre-existing runbook.

## 9. Endpoint SQLite/audit contract

The endpoint database persists incidents, runbooks and audit rows. Audit entries record concepts such as:

- input/policy check;
- classification;
- diagnosis;
- disagreement/reconciliation;
- runbook match;
- action permitted/blocked;
- remediation;
- verification;
- lifecycle/metrics;
- employee confirmation;
- escalation.

Historical enum/column names can remain for backwards compatibility; the current documentation should describe the behaviour that the running graded path actually uses.

## 10. Contract-change rule

Changes to any of the following require coordinated review because multiple surfaces depend on them:

- incident creation/confirmation semantics;
- SSE terminal result behaviour;
- Demo Lab state schema;
- runbook schema;
- safety/executor semantics;
- Service Desk ticket payload;
- support-level/closure semantics.

Presentation-only formatting may change without introducing a second contradictory source of lifecycle truth.
