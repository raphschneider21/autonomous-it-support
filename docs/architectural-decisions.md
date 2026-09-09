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

## Decision 2: AI Model — Google Gemini 2.5 Flash (Free)

**Choice**: Google Gemini 2.5 Flash via the `google-genai` Python library

**Why**:
- Free tier: 15 requests/minute, 1 million tokens/day — $0 cost
- Fast responses (~0.3s for classification tasks)
- Supports function calling / tool use for agent orchestration
- Good enough quality for a PoC demo
- No credit card required for the free tier

**Fallback**: If Gemini causes issues, switch to OpenAI GPT-4o-mini (~$0.01 for the entire demo).

**Model assignments per agent**:

| Agent | Model | Temperature | Max Tokens | Reasoning |
|---|---|---|---|---|
| Incident Commander | gemini-2.5-flash | 0.3 | 1024 | Needs structured, deterministic output |
| Triage Agent | gemini-2.5-flash | 0.2 | 512 | Classification must be consistent |
| Diagnostic Agent | gemini-2.5-flash | 0.1 | 1024 | Factual, read-only queries |
| Security Agent | gemini-2.5-flash | 0.0 | 512 | Zero creativity, strict policy enforcement |

**API key management**: Stored in `.env` file (never committed to Git). `.env.example` committed as a template.

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
pydantic==2.9.0
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

## Decision 14: Demo Determinism — Mock Triage & Executor (APPROVED)

**Choice**: The PoC runs `classify_from_mock` (deterministic word-based), and
all OS commands go through a stateful `MockExecutor`
(`src/executors/mock_executor.py`, `fixtures/mock_outputs.json`).

**Why**: Decision 2/6 already bound the team to mocks for development. For the
graded live demo, 100% reproducible traces are mandatory (rubric #8/#9).
Gemini (`gemini-2.5-flash`) is the documented production classification path
(Decision 2) with per-agent temperature/token settings; the engine calls it
through the same interface (`classify_from_mock` mirrors its signature), so
swapping to the real model is a config change, not an architecture change.

---

## Decision 15: Interface Contract Freeze (DRAFT — sign-off pending)

**Choice**: All cross-subsystem contracts frozen in `docs/schema.md`
(RunbookSchema, DiagnosticEvent SSE frames, EscalationTicket, IncidentReport,
SQLite schema).

**Why**: The three subsystems (engine, runbook store, client/escalation) were
built against these contracts. Rally the three to sign off (Milestone 1).
Post-freeze changes require a version bump + new ADR.

| # | Decision | Choice |
|---|---|---|
| 1 | Language | Python 3.11+ |
| 2 | AI Model | Google Gemini 2.5 Flash (Free) |
| 3 | Client UI | Local web app (browser) |
| 4 | Communication | REST API (JSON) |
| 5 | Database | SQLite (3 tables) |
| 6 | Dev Strategy | MockExecutor during development |
| 7 | Project Structure | Defined above |
| 8 | File Ownership | No overlaps, PR for shared files |
| 9 | Dependencies | 8 packages (listed above) |
| 10 | Git Workflow | Feature branches + PRs |
| 11 | API Keys | .env file, never committed |
| 12 | Round 2 Optimization | Runbook-store cache (mtime-invalidated) + diagnostic dedup; evidence artifacts immutable |
| 13 | Early-Exit Cache | REJECTED — would bypass per-incident audit trail |
| 14 | Demo Determinism | Mock triage + MockExecutor; Gemini via Decision 2 for production |
| 15 | Contract Freeze | Frozen in docs/schema.md; sign-off pending |
