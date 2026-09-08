---
trigger: model_decision
description: Architectural boundaries and module decoupling rules for the autonomous IT support agent.
---

# Architectural Invariants

The project is strictly decomposed into 4 decoupled subsystems to allow 3 developers to work simultaneously without conflict:

```
[Client UI] <---> [Core Brain / Engine] <---> [Knowledge & Runbooks]
                            |
                            v
                 [ITSM / Escalation Bridge]
```

### 1. Client UI (`src/client/`)
- Handles user triggers, consent banners, progress display, and confirmation prompts.
- Strictly presentation & user consent. Never contains direct OS execution code or raw LLM orchestration.
- Communicates with Core Engine via typed asynchronous events.

### 2. Core Engine & Executors (`src/engine/`, `src/executors/`)
- Houses the diagnostic loop, triage planner, and OS command executors (PowerShell, WMI, Bash).
- Enforces the Safety Gate before passing any instruction to an executor.
- All OS commands must run through an abstract executor interface (`IExecutor`) to support mock simulation during development.

### 3. Knowledge & Memory (`src/knowledge/`, `src/documentation/`)
- Manages the storage and retrieval of AI-Executable Runbooks and Human Incident Reports.
- Hosts the RAG retriever for enterprise legacy scripts, wiki articles, and diagnostic codes.
- Purely declarative input/output; does not execute OS commands directly.

### 4. ITSM Escalation Bridge (`src/integrations/`)
- Formats diagnostic findings and submits structured tickets to ticketing providers (ServiceNow, Jira, Zendesk).
- Never triggers remediations; only ingests completed or failed diagnostic sessions.
