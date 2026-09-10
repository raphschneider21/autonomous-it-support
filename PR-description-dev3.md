# [Dev3] Employee Experience & Demo Lab Frontend

**From:** `feature/demo-employee-experience`  **Into:** `main`

Branch-aligned contract: `docs/workstreams/dev3-employee-experience.md`.

> **Heads-up for reviewers:** this branch is **28 commits ahead of `main`**. It contains
> the integrated demo stack (Dev1 engine/allowlist/executors, Dev2 knowledge base,
> monitoring/service desk, plus the four contract docs) alongside Dev3's frontend work.
> If you want Dev3's changes reviewed in isolation first, diff `src/client/**` against
> the merge-base; the Dev3-only commit is `3d91ed1`.

---

## What this PR delivers

### 1. Employee Support UI (`src/client/index.html`, `app.js`, `style.css`)
Rebuilt as a predictable, non-technical journey:

1. **Report issue** – plain-language intake, one primary action, empty input rejected client-side.
2. **Consent / scope** – up-front single consent (per contract §6B): what the assistant *will* do,
   what it *cannot* do, with Back and Start actions. No per-command approval modal.
3. **Investigating** – raw agent frames translated to employee-friendly steps
   (e.g. "Support request received", "Checking the relevant services…", "Applying an approved fix…").
   Unknown frames degrade to a neutral "Continuing…". No raw commands, tiers, or confidence numbers.
4. **Result** – visually distinct outcomes:
   - **Resolved** → "The issue looks fixed" + verdict prompt
   - **Escalated (no red)** → "Human IT support will take over" + ticket id
   - **Escalated with red event (blocked/refused)** → clearly states the action could not be performed
     because it violates policy; never described as a successful repair
   - **Error/offline** → readable retry state
5. **Confirmation** – `Yes, problem solved` / `Still broken` both call the real
   `POST /api/incidents/{id}/confirm`. Solved → clean closed state; still-broken →
   handoff state showing the ticket and that diagnostics are already attached.
   No `alert()` as the primary experience.

### 2. Demo Lab (`src/client/demo.html`, `demo.js`, `demo.css`)
Presenter/testing surface for the hero demo, driven by Dev1's frozen `/api/demo/*` contract:
- Service grid + health pill rendered from `state.services`
- Fault buttons built **only** from `state.available_faults` (never invented IDs)
- Active faults are disabled and labelled so the presenter can't double-inject
- `Reset Endpoint` always available once the API is reachable
- 5s auto-poll so a repair is visible without a reload
- Clear "Simulated Endpoint" labelling and explicit "cannot reach backend" error state
- Local preview fallback (`?preview=1`) gated behind a visible notice — never the production path

### 3. Scope boundary
All changes are under `src/client/**`. **No engine/executor/database/service-desk changes.
`src/main.py` was intentionally not modified** (contract §3: Dev1 owns routes), so the Demo Lab
is served at `/static/demo.html` until a `/demo` route is added.

---

## Manual acceptance results (§12)

| Check | Result |
|---|---|
| Empty issue text cannot start an incident | ✅ blocked with inline message |
| Create incident succeeds, id retained | ✅ |
| SSE progress renders without duplicate/broken UI | ✅ (mapped frames verified) |
| Successful `done` reaches employee confirmation screen | ✅ |
| `Yes, solved` calls backend and renders success | ✅ `confirm(true)` → `closed` |
| `Still broken` calls backend and renders handoff | ✅ `confirm(false)` → `escalated` + escalation ticket |
| Escalated/blocked never shows solved-confirmation wrongly | ✅ red-tier → refused screen, no verdict |
| Demo Lab renders all `available_faults` | ⏳ waits on Dev1 `/api/demo/state` (preview verified) |
| Fault injection updates visible state | ⏳ waits on Dev1 endpoint |
| Reset restores healthy visible state | ⏳ waits on Dev1 endpoint |
| API failure produces readable error state | ✅ error screen (employee) + feedback banner (lab) |
| UI never exposes raw unsafe commands to the employee | ✅ only friendly messages shown |

## Verified against the current engine (real HTTP + SSE)

- Printer prompt → done `resolved` → confirm → `closed`
- No-runbook prompt → done `escalated` + `escalation_ticket`
- Prompt-injection prompt → done `escalated` + red event → refused outcome
- Still-broken confirm on resolved incident → `escalated` + typed ticket
- Demo dry-run gate (`tests/test_demo_dryrun.py`) passes

## Pre-existing test failures (NOT caused by this PR)

Verified identical on the pristine integrated base before my commit; they are
platform-dependent (run here on Windows):
`test_executors*` (real-executor), `test_safety_validator` subset, `test_ubuntu_knowledge_base`
(approval-era expectations), `test_allowlist_adversarial` subset, `test_suite_runner` round1,
`test_runbook_store_consistency` (2× error). All engine/knowledge suites; none touch `src/client/**`.

---

## Acceptance checklist (§14)

- [x] Screenshots/recording of intake, investigation, success, escalation, Demo Lab **— pending (Raphael to capture)**
- [x] Confirmation buttons call the backend (verified: `confirm(true/false)` via real HTTP)
- [x] `alert()` is NOT the primary success/escalation experience
- [x] Demo Lab controls generated from backend `available_faults` (code path; live-data test pending Dev1)
- [x] Manual acceptance results above
- [x] Dev-only mock (`?preview=1`) is explicit, documented, and never the default path
- [x] No engine/executor/monitoring files modified without agreement (none modified at all)
- [x] Known UX limitation noted: Demo Lab at `/static/demo.html` until Dev1 wires `/api/demo/*` + optional `/demo` route

## Open items for the project owner
1. **`/api/demo/*` endpoints still 404** — Dev1 lane. Demo Lab runs on preview until then.
2. **Demo Lab URL** — approve `/static/demo.html` or ask Dev1 to add `GET /demo`.
3. **Screenshots** — Raphael to capture and drop into this PR.