# Architectural Decisions — Binding for All Developers

**Date**: 2026-09-08
**Status**: APPROVED — All 3 developers must follow these decisions.

---

## Decision 1: Programming Language — Python 3.11+

**Choice**: Python

**Why**:
- Beginner-friendly (Dev2 can read and understand the code)
- `subprocess` module runs PowerShell and Bash commands natively
- `sqlite3` is built into Python — zero setup
- FastAPI generates a REST API with almost no boilerplate
- `pytest` makes testing simple
- The AI assistant writes all the code; Python is the easiest language for AI to generate correctly

**Forbidden**: No JavaScript/TypeScript for backend. No Go. No Java.

---

## Decision 2: AI Model — Claude, one model chosen per agent (SUPERSEDES the Gemini decision)

**Choice**: Anthropic Claude via the `anthropic` Python SDK, with a different
model per runtime agent.

**Why a mix rather than one model**: the four agents do genuinely different
work. Sorting one user sentence into a category and reasoning from raw
`journalctl` output to an unscripted root cause are not the same task, and
pricing one for the other means either overpaying for the first or
under-serving the second. Choosing per agent is also what the rubric's "argued
model selection" asks for — an argument requires a choice to have been made.

| Agent | Model | Max tokens | Thinking | Effort | Reasoning |
|---|---|---|---|---|---|
| Triage Agent | `claude-haiku-4-5` | 512 | off | n/a | One sentence into one of ten categories. Cheapest capable model; Haiku 4.5 does not accept `effort`, and thinking would add latency to a task that needs none. |
| Diagnostic Agent | `claude-opus-5` | 2048 | adaptive | medium | Reads raw `journalctl`/`df`/`systemctl` output and reasons to a root cause nobody wrote a runbook for. The only genuinely hard judgement in the system. Effort held at medium so the 30-second budget survives. |
| Security Agent | `claude-haiku-4-5` | 512 | off | n/a | Pattern recognition over the prompt and the diagnostic evidence. Runs concurrently with Diagnostic, so its latency is free in wall-clock terms. |
| Incident Commander | `claude-sonnet-5` | 1024 | adaptive | low | Reconciles two structured assessments. Real judgement over a small, well-shaped input. |

Settings live in `src/engine/llm.py` (`AGENTS`), and `llm.model_table()` renders
this table from the code, so the document cannot drift from what runs.

**Why not Gemini 2.5 Flash** (the original decision): the free tier's 15
requests/minute is 3.75 incidents/minute at four calls each, which is tight for
a test-suite run and leaves no headroom during a recorded demo. The team has an
Anthropic API key, and at roughly $0.03 per incident the whole project costs
tens of francs — the constraint was never really cost.

**Why not a local model** (Ollama on the presenter's Mac): genuinely
attractive — endpoint telemetry never leaves the machine, which is a real
enterprise and GDPR argument, and it removes network dependency from a recorded
demo. Rejected for the 30-second budget: four agents queue on one GPU, and an
8B model needs roughly 15–20 seconds for the Diagnostic call alone. Worth
revisiting as a measured Round 2 comparison.

**Concurrency**: Triage runs first, then Diagnostic and Security in parallel,
then the Commander. Sequential calls do not fit the budget; this shape does.

**Every call has a declared fallback.** With no `ANTHROPIC_API_KEY` each agent
uses a deterministic path (keyword classification, heuristic assessment,
rule-based reconciliation) and the test suite runs unchanged. `_source` on every
agent result records which path ran, so the TDD reports the split rather than
assuming it.

**API key management**: `.env`, never committed. `.env.example` is the template.

---

## Decision 3: Client UI — Local Web App (Browser)

**Choice**: A web app served locally on `http://localhost:8000`, opened in the user's browser.

**Tech stack**:
- **Backend**: FastAPI (Python) serves the API + static HTML files
- **Frontend**: Plain HTML + CSS + vanilla JavaScript (no React, no Vue, no frameworks)
- **Styling**: Simple CSS, clean layout, no design library needed

**Why**:
- Opens in any browser — easy to demo
- Screenshots are trivial for the TDD
- No installation needed beyond Python
- The beginner can understand HTML/CSS visually
- FastAPI auto-generates API docs at `/docs` (useful for the live demo "under the hood" segment)

**UI states** (3 screens Dev3 builds):
1. **Intake Screen**: Problem description input + category dropdown + "Start Diagnostics" button
2. **Live Progress Screen**: Real-time event feed showing agent actions + "Emergency Stop" button + consent modal for Yellow-tier actions
3. **Resolution Screen**: "Did this fix your issue?" with Yes/No buttons + generated report display

---

## Decision 4: Communication — REST API (JSON)

**Choice**: REST API with JSON payloads between Frontend and Backend.

**Endpoints**:

```
POST   /api/incidents              — Submit a new incident
GET    /api/incidents/{id}         — Get incident status + event log
POST   /api/incidents/{id}/approve — User approves a Yellow-tier action
POST   /api/incidents/{id}/cancel  — User cancels the session
GET    /api/runbooks               — List stored runbooks
GET    /api/health                 — System health check
```

**Why**: Simple, inspectable during demo, well-supported by FastAPI, no WebSocket complexity needed.

---

## Decision 5: Database — SQLite (3 Tables)

**File**: `data/incidents.db`

**Schema**:

```sql
-- Table 1: Incident records
CREATE TABLE incidents (
    id TEXT PRIMARY KEY,              -- e.g. "INC-20260908-001"
    created_at TEXT NOT NULL,         -- ISO 8601 timestamp
    user_prompt TEXT NOT NULL,        -- What the user typed
    category TEXT,                    -- "network", "printer", "office", "legacy", "frozen"
    severity TEXT,                    -- "low", "medium", "high", "critical"
    status TEXT DEFAULT 'open',       -- "open", "diagnosing", "awaiting_approval", "resolved", "escalated"
    hostname TEXT,
    os_version TEXT,
    resolution_summary TEXT,
    runbook_id TEXT,                  -- FK to runbooks table, NULL if no runbook matched
    FOREIGN KEY (runbook_id) REFERENCES runbooks(id)
);

-- Table 2: AI-Executable Runbooks
CREATE TABLE runbooks (
    id TEXT PRIMARY KEY,              -- e.g. "RB-PRINT-001"
    title TEXT NOT NULL,
    target_os TEXT,
    tags TEXT,                        -- JSON array stored as text
    trigger_signatures TEXT,          -- JSON object stored as text
    pre_checks TEXT,                  -- JSON array stored as text
    remediation_steps TEXT,           -- JSON array stored as text
    verification TEXT,                -- JSON array stored as text
    rollback_plan TEXT,               -- JSON array stored as text
    created_at TEXT NOT NULL,
    times_executed INTEGER DEFAULT 0,
    times_succeeded INTEGER DEFAULT 0
);

-- Table 3: Audit Log (every action the agent takes)
CREATE TABLE audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    incident_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,          -- ISO 8601
    agent_name TEXT NOT NULL,         -- "IncidentCommander", "TriageAgent", etc.
    action_type TEXT NOT NULL,        -- "diagnosis", "remediation", "escalation", "blocked"
    safety_tier TEXT NOT NULL,        -- "green", "yellow", "red"
    command_executed TEXT,            -- The actual command or "N/A"
    output TEXT,                      -- Command output or agent reasoning
    user_approved INTEGER DEFAULT 0, -- 1 if user clicked Approve, 0 otherwise
    FOREIGN KEY (incident_id) REFERENCES incidents(id)
);
```

**Why SQLite**: Zero configuration, single file, built into Python, sufficient for a PoC with hundreds (not millions) of records.

---

## Decision 6: Mock Strategy — MockExecutor During Development

**Rule**: During development and testing, ALL OS commands go through `MockExecutor`. No real PowerShell/Bash commands run until the final demo rehearsal.

**Interface**:

```python
from abc import ABC, abstractmethod

class IExecutor(ABC):
    @abstractmethod
    def run(self, command: str, timeout: int = 30) -> dict:
        """Returns {"exit_code": int, "stdout": str, "stderr": str}"""
        pass
```

**Implementations**:
- `MockExecutor` — Returns predefined outputs from a fixtures file. Used during development.
- `RealExecutor` — Runs actual commands via `subprocess.run()`. Used only during demo.

**Mock data file**: `fixtures/mock_outputs.json` — Maps command strings to fake outputs.

---

## Decision 7: Project Structure

```
autonomous-it-support/
├── src/
│   ├── __init__.py
│   ├── main.py                     # FastAPI app entry point
│   ├── models.py                   # Pydantic models (shared schemas)
│   ├── database.py                 # SQLite connection + table creation
│   ├── engine/
│   │   ├── __init__.py
│   │   ├── incident_commander.py   # Orchestrator agent
│   │   ├── triage_agent.py         # Classification agent
│   │   ├── diagnostic_agent.py     # Read-only diagnostics agent
│   │   └── security_agent.py       # Policy enforcement agent
│   ├── executors/
│   │   ├── __init__.py
│   │   ├── executor_interface.py   # IExecutor abstract class
│   │   ├── mock_executor.py        # MockExecutor for dev
│   │   └── real_executor.py        # RealExecutor for demo
│   ├── knowledge/
│   │   ├── __init__.py
│   │   ├── runbook_parser.py       # Loads YAML runbooks
│   │   └── runbook_matcher.py      # Matches symptoms to runbooks
│   ├── documentation/
│   │   ├── __init__.py
│   │   ├── runbook_generator.py    # Creates new runbooks from resolved incidents
│   │   └── report_generator.py     # Creates Markdown incident reports
│   ├── integrations/
│   │   ├── __init__.py
│   │   └── escalation.py           # Formats escalation ticket JSON
│   └── safety/
│       ├── __init__.py
│       └── safety_validator.py     # Checks commands against Green/Yellow/Red tiers
├── src/client/
│   ├── index.html                  # Main UI
│   ├── style.css                   # Styling
│   └── app.js                      # Frontend JavaScript (fetch API calls)
├── fixtures/
│   ├── runbooks/                   # YAML runbook files
│   │   ├── cisco-vpn-stuck-adapter.yaml
│   │   ├── windows-print-spooler-crash.yaml
│   │   └── legacy-vbscript-missing-drive.yaml
│   └── mock_outputs.json           # Mock executor responses
├── tests/
│   ├── test_safety_validator.py
│   ├── test_runbook_parser.py
│   ├── test_runbook_matcher.py
│   ├── test_triage_agent.py
│   └── test_suite.json             # 10-incident test scenarios
├── data/
│   └── incidents.db                # SQLite database (created at runtime)
├── docs/                           # (already exists)
├── .agents/rules/                  # (already exists)
├── .env.example                    # API key template
├── .gitignore
├── requirements.txt                # Python dependencies
├── GEMINI.md
├── TEAM_QUICKSTART.md
└── README.md
```

---

## Decision 8: File Ownership (No Overlaps)

| Developer | Owns These Paths | Can Read (Not Edit) |
|---|---|---|
| **Dev1** | `src/engine/`, `src/safety/`, `src/executors/` | Everything in `src/` |
| **Dev2** | `src/knowledge/`, `src/documentation/`, `fixtures/runbooks/` | Everything in `src/` |
| **Dev3** | `src/client/`, `src/integrations/`, `src/main.py`, `src/models.py`, `src/database.py` | Everything in `src/` |

**Shared files** (edited only by one person at a time, communicated in Teams chat):
- `src/models.py` — Dev3 owns, but Dev1/Dev2 request changes via PR
- `src/database.py` — Dev3 owns
- `requirements.txt` — Dev1 owns
- `fixtures/mock_outputs.json` — Dev2 owns
- `tests/` — Each dev writes tests for their own subsystem

---

## Decision 9: Python Dependencies

```
# requirements.txt
fastapi==0.115.0
uvicorn==0.30.0
google-genai==1.0.0
pyyaml==6.0.2
pydantic>=2.12             # 2.12+ ships cp314 wheels (Ubuntu 26.04 = Python 3.14)
python-dotenv==1.0.1
pytest==8.3.0
httpx==0.27.0              # For testing FastAPI endpoints
```

**Install command**: `pip install -r requirements.txt`

---

## Decision 10: Git Workflow

1. **Never push to `main`** directly
2. Create branch: `feature/dev1-safety-validator`, `feature/dev2-runbook-matcher`, `feature/dev3-client-ui`
3. Commit often (every 30-60 minutes of work)
4. Push to your branch
5. Open a Pull Request to merge into `main`
6. At least 1 other dev must review before merge
7. Pull `main` before starting work each day: `git pull origin main`

**Commit message format**: `dev1: describe what you did` / `dev2: describe what you did` / `dev3: describe what you did`

---

## Decision 11: API Key Setup

1. Each developer goes to https://aistudio.google.com/apikey
2. Sign in with a Google account
3. Click "Create API Key"
4. Copy the key
5. Copy `.env.example` to `.env`
6. Paste your key into `.env` as `GOOGLE_API_KEY=your_key_here`
7. Never commit `.env` to Git (it's in `.gitignore`)

---

## Decision 12: Round 2 Optimization — Runbook-Store Cache (APPROVED 2026-09-09)

**Choice**: Cache the parsed YAML runbook list in-process, invalidating via mtime
(`src/knowledge/runbook_parser.py`). Also deduplicate identical diagnostic
commands within a single pass (`src/engine/diagnostic_agent.py`).

**Why**: Every incident previously re-opened + re-parsed all runbook YAML from
disk during matching. Measured effect (TDD §5, `docs/benchmark-round2.md`):
avg latency **6.5 → 3.3 ms (-49%)**, accuracy and tool-call count unchanged.

**Evidence inviolability**: benchmark artifacts (`data/benchmarks/round*.json`)
are only written when explicitly regenerated via `--round`; the pytest wrapper
uses `write=False`. Motivation: a routine test run had silently overwritten the
"Before" baseline (6.5 → 4.4 ms), which would have invalidated the TDD
comparison.

---

## Decision 13: Recurring-Incident Early-Exit — REJECTED

**Proposal considered**: a normalized-prompt hash cache so repeated incidents
skip triage + diagnostics and jump straight to the known runbook plan.

**Decision**: Rejected. Skipping triage/diagnostics on repeats would drop the
per-incident audit evidence (input check, classification, diagnostic outputs)
that the graded rubric's "auditability" and TDD §3/§5 evidence require. The
service-relevant win is already captured by the runbook-load cache (Decision
12), which costs no audit data. Trade-off accepted: ~3 ms extra latency per
repeat incident in exchange for a complete, defensible audit trail.

---

## Decision 14: Deterministic fallbacks, not mocks in place of the model (REVISED)

**Choice**: The four agents call Claude (Decision 2). Each one also has a
deterministic fallback — `classify_from_mock` for triage, a heuristic assessment
for diagnosis, keyword indicators for security, and the rule-based
`reconcile_assessments` for the Commander. The fallback runs when no
`ANTHROPIC_API_KEY` is configured, when a call fails, or when a response is not
usable. `MockExecutor` still stands in for OS commands during development and
rehearsal.

**Why the revision**: the earlier version of this decision described the mock
classifier as the demo path and the model as a future config change. That
reading is what left the project with no generative AI in it at all while the
documentation described temperatures for calls that were never made. The
fallback is a resilience path, not the primary one.

**Why keep fallbacks at all**: the test suite must run without an API key, on
CI and on a laptop that has none; and a model outage during a recorded demo
should degrade the system rather than end it. `_source` on every agent result
records which path ran, so the TDD reports the split as measured evidence
rather than assuming it.

---

## Decision 15: Interface Contract Freeze (DRAFT — sign-off pending)

**Choice**: All cross-subsystem contracts frozen in `docs/schema.md`
(RunbookSchema, DiagnosticEvent SSE frames, EscalationTicket, IncidentReport,
SQLite schema).

**Why**: The three subsystems (engine, runbook store, client/escalation) were
built against these contracts. Rally the three to sign off (Milestone 1).
Post-freeze changes require a version bump + new ADR.

---

## Decision 16: Knowledge Base Split Into Platform Stores (APPROVED — `@Dev2`)

**Choice**: Runbooks live in per-platform **stores**. `fixtures/runbooks/`
remains the `default` store (3 Windows fixtures, existing engine + live demo);
`fixtures/runbooks/ubuntu-26.04/` is the `ubuntu-26.04` store (30 runbooks).
`load_all_runbooks()` / `match_runbook()` take an optional `store`; with no
argument they read `$RUNBOOK_STORE` and default to `default`.

**Why**: The team's training dataset targets Ubuntu 26.04, but the engine, the
E2E suite and the rehearsed live demo are all built on the Windows fixtures.
A single flat store would have put "print jobs stuck in the queue" in front of
both `RB-PRINT-001` (Windows spooler) and `RB-CUPS-001` (Ubuntu CUPS), making
retrieval ambiguous and breaking `tests/test_e2e.py`. Separate stores let the
Ubuntu knowledge base be built and benchmarked in full without touching the
demo path; the cutover is one environment variable once `@Dev1` has converted
the triage and diagnostic agents to Linux.

**Rejected**: replacing the Windows fixtures outright — would have broken the
rehearsed demo and 3 E2E tests mid-milestone.

---

## Decision 17: Runbook Retrieval Is Deterministic, Not an LLM Call (APPROVED — `@Dev2`)

**Choice**: Symptom -> runbook matching is IDF-weighted lexical scoring with an
explicit confidence floor (0.35) and runner-up margin (0.08), not a model call.
`match_runbook` returns `None` — meaning *escalate* — when either gate fails.

**Why**: Retrieval runs on every incident and decides whether to execute a
remediation on a user's machine. An LLM call would add latency and token cost
to a lookup, introduce run-to-run variance into an audit trail that has to be
defensible, and yield a confidence number that cannot be explained to a
reviewer. Measured: 100% on 36 held-out paraphrases, **0 wrong-runbook
matches**, p95 0.15 ms (`data/benchmarks/retrieval-round1.json`).

The previous word-overlap matcher had no abstention path at all — it returned
its best guess for every input, including a cracked screen (-> `RB-APT-005`,
would have run `sudo dpkg --configure -a`) and a privilege-escalation prompt
(-> `RB-AUDIO-004`). It scored 69.4% with **11 unsafe matches** on the same set.

**Revisit when**: corpus > ~200 runbooks, or held-out accuracy < 90%
(`docs/rag-ingestion-strategy.md` §6).

---

## Decision 18: RunbookSchema v1.1 — `parameters`, `environment`, `source_case` (APPROVED — `@Dev2`)

**Choice**: Additive, backward-compatible bump. `parameters` declares
`{placeholder}` values resolved from defaults at load time; `environment`
declares `vm-safe` vs `physical-only`; `source_case` back-references the
training dataset.

**Why**: Without `parameters`, a runbook has to hard-code one machine's values
(a specific audio sink ID, monitor connector, or block device), which makes it
a single-machine script rather than reusable knowledge. Resolution happens in
the knowledge layer, so executors still receive concrete commands and **no
engine change was required**. `environment` records that a VM endpoint has no
Wi-Fi radio, touchpad or backlight, so those runbooks are documented as
untestable on the demo VM rather than silently failing.

**Impact**: v1.0 fixtures parse unchanged (all three fields optional).

---

## Decision 19: Safety Tiers Extended to Ubuntu 26.04 (APPROVED — `@Dev2`, needs `@Dev1` review)

**Choice**: `src/safety/safety_validator.py` gains Ubuntu Green/Yellow/Red
patterns, a blanket `sudo` -> Yellow rule, and **most-specific-pattern-wins**
resolution (Red still absolute).

**Why**: This was a live safety hole, not a nicety. Before the change, 45 of
the 59 Ubuntu remediation commands classified **Green** — auto-executed with no
human approval — including `sudo dpkg --configure -a`,
`sudo mount -o remount,rw /`, `sudo modprobe -r psmouse` and `gdctl set`. The
validator only knew PowerShell patterns, and `validate_command` defaulted
anything unrecognised to Green.

Specificity resolution is what makes the blanket `sudo` rule usable: read-only
elevated diagnostics (`sudo apt-get check`, `sudo dpkg --audit`, `sudo fuser`)
are listed in Green and win on pattern length, so they are not needlessly
gated. It also preserves the existing Windows behaviour that
`ipconfig /all` is Green while `ipconfig /flushdns` is Yellow.

**After**: 49 of 59 remediation steps are Yellow (approval-gated); the
remaining 10 are provably read-only inspection steps. All 17 of `@Dev1`'s
existing safety tests still pass. **`@Dev1` owns this file — please review;
this change is isolated in its own commit and can be dropped independently.**

---

| # | Decision | Choice |
|---|---|---|
| 1 | Language | Python 3.11+ |
| 2 | AI Model | Claude, one model chosen per agent (Haiku 4.5 / Opus 5 / Sonnet 5) |
| 3 | Client UI | Local web app (browser) |
| 4 | Communication | REST API (JSON) |
| 5 | Database | SQLite (3 tables) |
| 6 | Dev Strategy | MockExecutor during development |
| 7 | Project Structure | Defined above |
| 8 | File Ownership | No overlaps, PR for shared files |
| 9 | Dependencies | 8 packages (pydantic >= 2.12 for Python 3.14 / Ubuntu 26.04) |
| 10 | Git Workflow | Feature branches + PRs |
| 11 | API Keys | .env file, never committed |
| 12 | Round 2 Optimization | Runbook-store cache (mtime-invalidated) + diagnostic dedup; evidence artifacts immutable |
| 13 | Early-Exit Cache | REJECTED — would bypass per-incident audit trail |
| 14 | Demo Determinism | MockExecutor for rehearsal; Claude per Decision 2, with declared deterministic fallbacks |
| 15 | Contract Freeze | Frozen in docs/schema.md; sign-off pending |
| 16 | Knowledge Stores | Per-platform runbook stores; `$RUNBOOK_STORE` selects |
| 17 | Retrieval | Deterministic IDF matching + abstention; no LLM call |
| 18 | RunbookSchema v1.1 | `parameters`, `environment`, `source_case` (additive) |
| 19 | Safety Tiers | Ubuntu patterns + specificity resolution (`@Dev1` review) |
