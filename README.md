# Autonomous Enterprise IT Support Agent (Tier 1)

[![FHNW Generative AI Project](https://img.shields.io/badge/FHNW-Generative_AI_Project-blue.svg)](https://www.fhnw.ch)
[![Status](https://img.shields.io/badge/Status-Milestone_0:_Design-green.svg)]()
[![Target](https://img.shields.io/badge/Demonstration-15_Min_Live_PoC-orange.svg)]()

An autonomous, multi-agent IT support desktop troubleshooter for enterprise workstations. Designed and implemented for the **FHNW University Generative AI Project** (Submission: September 30, 2026).

The agent diagnoses endpoint issues, safely executes remediations, produces dual-format documentation (AI-executable YAML Runbooks and human-readable Markdown post-mortems), and cleanly escalates unresolvable issues to Tier 2/3 human IT staff.

---

## 🚀 Team Quickstart
Are you a collaborating developer joining this project?  
👉 **Read the [Team Onboarding & Setup Guide](TEAM_QUICKSTART.md)** to clone the repo, connect your AI agent, and claim your role.

---

## 🎯 Executive Summary & Value Proposition

Enterprise service desks waste substantial time manually resolving repetitive Tier-1 issues: collecting workstation telemetry, investigating DNS/VPN drops, clearing print queues, and purging corrupted authentication tokens. 

This solution replaces slow manual ticketing with a **transparent, multi-agent autonomous system** that:
1. **Investigates & Diagnoses**: Gathers endpoint telemetry and consults enterprise knowledge bases in parallel.
2. **Safely Remediates**: Executes non-destructive actions and mandates **human approval** for state-altering changes.
3. **Generates Dual Documentation**:
   - **AI-Executable Runbooks** (YAML/JSON) to deterministically solve recurring incidents with zero hallucination.
   - **Human Incident Reports** (Markdown) providing a timestamped audit trail for IT management.
4. **Escalates Cleanly**: Pre-packages full diagnostic telemetry into structured Tier-2 tickets when an issue requires human specialist intervention.

---

## 🏛️ Multi-Agent Architecture

The runtime system operates with **4 specialized agents** with explicit separation of concerns:

```
                  ┌─────────────────────────────────────┐
                  │    User Incident Submission (UI)    │
                  └──────────────────┬──────────────────┘
                                     │
                                     ▼
                  ┌─────────────────────────────────────┐
                  │         Incident Commander          │
                  │  (Coordinates workflow & consensus) │
                  └──────┬───────────┬───────────┬──────┘
                         │           │           │
          ┌──────────────┘           │           └──────────────┐
          ▼                          ▼                          ▼
┌──────────────────┐       ┌──────────────────┐       ┌──────────────────┐
│   Triage Agent   │       │ Diagnostic Agent │       │  Security Agent  │
│ (Classification, │       │ (Service checks, │       │ (Safety tiers,   │
│  severity & SLA) │       │  knowledge RAG)  │       │  policy guards)  │
└──────────────────┘       └──────────────────┘       └──────────────────┘
          │                          │                          │
          └──────────────┬───────────┴───────────┬──────────────┘
                         │
                         ▼
        ┌───────────────────────────────────┐
        │ Human Approval Gate (Yellow Tier) │
        └─────────────────┬─────────────────┘
                          │
                          ▼
        ┌───────────────────────────────────┐
        │  Local Tools & SQLite Persistence │
        │ (Runbook Execution & Audit Logs)  │
        └───────────────────────────────────┘
```

1. **Incident Commander**: Interprets requests, coordinates parallel investigations, detects disagreements between agents, enforces human approval, and issues final resolution proposals.
2. **Triage Agent**: Classifies category, assesses severity, extracts structured symptoms, and identifies duplicate/related tickets.
3. **Diagnostic Agent**: Executes read-only telemetry queries, tests connectivity, and matches symptoms against existing runbooks.
4. **Security & Policy Agent**: Audits every proposed remediation against organizational policy, verifies permission tiers (Green/Yellow/Red), flags prompt injections, and blocks dangerous actions.

---

## 📋 Academic Requirements & Grading Alignment

This project is engineered to achieve the **"Exceeded" (10/10)** standard across all 10 evaluation criteria defined in the FHNW grading rubric:

| Category | Criterion | Repository Artifacts & Evidence |
|:---|:---|:---|
| **Business Case** | Quantified impact, ROI, time/cost savings | [`docs/problem-scope.md`](./docs/problem-scope.md), TDD Section 1 |
| **Agents** | 4 named agents, best practices, argued models/settings | [`docs/user-journey.md`](./docs/user-journey.md), [`.agents/rules/grading-rubric.md`](./.agents/rules/grading-rubric.md) |
| **Tools** | Diagnostic commands, service control, SQLite storage | [`docs/documentation-model.md`](./docs/documentation-model.md), TDD Section 2 |
| **Efficiency** | Speed, cost, latency, token optimization (Before vs. After) | `tests/` benchmark suites, TDD Section 5 |
| **Implementation** | Documented progress, iterations, failed attempts | Git history, TDD Section 4 |
| **Experimentation** | 2+ test cycles, realistic & malicious edge cases | `tests/` test repository, TDD Section 3 & 5 |
| **Reflections** | Deep technical and architectural learnings | TDD Section 6 |
| **Business Demo** | End-to-end incident lifecycle tied to ROI | [`.agents/rules/live-demo-spec.md`](./.agents/rules/live-demo-spec.md) |
| **Technology Demo** | Traces, tool calling, agent disagreements under the hood | [`.agents/rules/live-demo-spec.md`](./.agents/rules/live-demo-spec.md) |
| **Ethics & Safety** | Safety gates, human consent, prompt injection guardrails | [`.agents/rules/safety.md`](./.agents/rules/safety.md) |

For comprehensive rubric mappings, see [`docs/grading-and-deliverables.md`](./docs/grading-and-deliverables.md).

---

## 🛡️ Safety & Execution Tiers

Every operation proposed by an agent is evaluated against hard safety boundaries:
- **Tier 1 (Green - Auto-Approved)**: Read-only diagnostic checks (`Get-Service`, `ping`, `ipconfig`, Event Log queries).
- **Tier 2 (Yellow - Human Consent Required)**: Non-destructive local modifications (service restarts, DNS cache flushes, cache clears).
- **Tier 3 (Red - Strictly Blocked)**: High blast-radius actions (modifying admin credentials, altering firewall/EDR rules, deleting system folders, prompt injection attempts).

---

## 📁 Repository Structure

```
├── .agents/
│   └── rules/                  # Development and runtime invariants
│       ├── grading-rubric.md   # FHNW rubric criteria & "Exceeded" mandates
│       ├── tdd-and-evidence.md # TDD structure & real-time evidence protocol
│       ├── live-demo-spec.md   # 15-minute live demo cadence & script
│       ├── safety.md           # Green/Yellow/Red execution safety tiers
│       ├── architecture.md     # Decoupled subsystem boundaries
│       └── team-conventions.md # Git workflow & token hygiene
├── docs/
│   ├── grading-and-deliverables.md  # Course criteria mapping & deliverables
│   ├── problem-scope.md             # Business problem & incident taxonomy
│   ├── documentation-model.md       # AI Runbooks & Human Incident Reports specs
│   ├── user-journey.md              # Sequence flows & escalation protocol
│   └── roadmap.md                   # Team task board & sprint milestones
├── src/                        # Application source code
├── tests/                      # Automated test suites & performance benchmarks
├── GEMINI.md                   # AI agent entrypoint & operational rules
├── TEAM_QUICKSTART.md          # Collaborator onboarding guide
└── README.md                   # Project overview & navigation
```

---

## 👥 Team & Ownership

| Developer | Role & Subsystem Ownership | Primary Focus Areas |
|:---|:---|:---|
| **`@Dev1`** | Core Engine & Safety Gates | Orchestration engine, safety validation, executor interfaces |
| **`@Dev2`** | Knowledge Base & Documentation | Runbook parser/matcher, incident reporting, RAG integration |
| **`@Dev3`** | Client UI & ITSM Bridge | Frontend interface, live event streaming, escalation tickets |
