# Autonomous Enterprise IT Support Agent (Tier 1)

## Project Overview
This repository contains the implementation of an autonomous, AI-driven Tier-1 IT Support system designed for enterprise endpoints as part of the FHNW Generative AI module. 

The system acts as a reliable first-responder for workstation issues (network/VPN failures, print spooler crashes, credential lockups, and legacy internal tooling errors). It autonomously diagnoses issues, executes safe remediations under human oversight, produces **Dual-Documentation** (AI-Executable Runbooks + Human Incident Reports), and escalates complex incidents cleanly to Tier 2/3 human IT staff.

---

## 🌟 Team Profile & AI Communication Guidelines
- **Audience**: The three developers on this team are **beginners/inexperienced in coding**.
- **Plain English**: Explain all concepts, diagnostics, and architectures simply and in plain English. Never use unnecessary technical jargon. If a technical term is essential, explain what it means in everyday language.
- **AI Owns the Code**: The AI assistant is responsible for writing, formatting, testing, and fixing the code. Do not expect the developers to write code or debug syntax errors manually.
- **Proactive Guidance**: The AI must proactively propose the next logical, bite-sized step. When a decision is needed, present clear, understandable options rather than asking open-ended technical questions.

---

## Academic Context & Standing Deliverables

All work in this repository is strictly governed by the authoritative FHNW course requirements:
- **Final Submission Deadline**: 30 September 2026 at 23:59
- **Deliverable 1**: 15-minute Live Proof-of-Concept Demonstration (Recorded)
- **Deliverable 2**: Technical Design Document (TDD) adhering to the official template

All development agents and contributors must target the **"Exceeded" (10/10 points)** standard across all 10 rubric categories documented in [`docs/grading-and-deliverables.md`](./docs/grading-and-deliverables.md) and [`.agents/rules/grading-rubric.md`](./.agents/rules/grading-rubric.md).

---

## Living Documentation Index (Single Source of Truth)

All agents and team members MUST treat these files as the authoritative project guides:
- **Team Onboarding & Setup**: [`TEAM_QUICKSTART.md`](./TEAM_QUICKSTART.md)
- **Academic Requirements & Grading Matrix**: [`docs/grading-and-deliverables.md`](./docs/grading-and-deliverables.md)
- **Problem Scope & Boundaries**: [`docs/problem-scope.md`](./docs/problem-scope.md)
- **Dual-Documentation Model (Runbooks & Reports)**: [`docs/documentation-model.md`](./docs/documentation-model.md)
- **User Journey & Escalation Protocol**: [`docs/user-journey.md`](./docs/user-journey.md)
- **Team Task Board & Milestones**: [`docs/roadmap.md`](./docs/roadmap.md)

### Agent Rule System (`.agents/rules/`)
- [`.agents/rules/grading-rubric.md`](./.agents/rules/grading-rubric.md): 10 evaluation criteria and "Exceeded" mandates.
- [`.agents/rules/tdd-and-evidence.md`](./.agents/rules/tdd-and-evidence.md): TDD structure, live screenshot capture, and metric logging rules.
- [`.agents/rules/live-demo-spec.md`](./.agents/rules/live-demo-spec.md): 15-minute live demonstration cadence and under-the-hood inspection script.
- [`.agents/rules/safety.md`](./.agents/rules/safety.md): Green/Yellow/Red execution safety tiers and hard blocks.
- [`.agents/rules/architecture.md`](./.agents/rules/architecture.md): Decoupled subsystem boundaries (UI, Engine, Knowledge, ITSM).
- [`.agents/rules/team-conventions.md`](./.agents/rules/team-conventions.md): Git branching, PR reviews, and token hygiene.

---

## Core Engineering Rules of Engagement

1. **Safety First**: Adhere strictly to the execution safety tiers in `.agents/rules/safety.md`. Destructive or administrative commands without human consent are strictly prohibited.
2. **Runtime vs. Development Agents**: Distinguish clearly between the runtime agents inside the application (Incident Commander, Triage, Diagnostic, Security) and development tools (Antigravity, Codex).
3. **Capture Evidence Live**: Do not reconstruct experiments retroactively. Capture screenshots, prompt variations, execution latencies, token consumption, and failed attempts as they happen.
4. **Target the Live Demo**: Structure all workflows with the 15-minute live demonstration in mind (visible agent traces, disagreement resolution, human approval gate, prompt injection refusal).
5. **Filesystem Over Chat Memory**: Document all architectural decisions, schema changes, and measurement data in `docs/` or `tests/`.
6. **Token & Context Hygiene**: Keep queries focused on individual documents or modules to maximize performance on free model tiers.
