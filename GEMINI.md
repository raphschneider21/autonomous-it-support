# Autonomous Enterprise IT Support Agent (Tier 1)

## System Overview
This project builds an autonomous, AI-driven Tier-1 IT Support desktop agent for enterprise endpoints. It acts as an automated "troubleshooter that actually works," directly diagnosing and remediating common workstation issues (network/VPN drops, hung print spoolers, credential/cache lockups, and legacy in-house script executions). 

Upon resolution, the agent produces a **Dual-Documentation** output:
1. **AI-Executable Runbook** (structured JSON/YAML) to instantly re-solve the issue in the future.
2. **Human-Readable Incident Report** (plain-text Markdown) for enterprise IT auditability.

If the issue cannot be safely resolved, the agent packages telemetry and attempted steps into a clean escalation ticket for Tier 2/3 human IT support.

---

## 🌟 Team Profile & AI Communication Guidelines
- **Audience**: The three developers on this team are **beginners/inexperienced in coding**.
- **Plain English**: Explain all concepts, diagnostics, and architectures simply and in plain English. Never use unnecessary technical jargon. If a technical term is essential, explain what it means in everyday language.
- **AI Owns the Code**: The AI assistant is responsible for writing, formatting, testing, and fixing the code. Do not expect the developers to write code or debug syntax errors manually.
- **Proactive Guidance**: The AI must proactively propose the next logical, bite-sized step. When a decision is needed, present clear, understandable options rather than asking open-ended technical questions.

---

## Living Documentation Index
All agents and team members MUST treat these files as the Single Source of Truth:
- **Problem Scope & Safety Gates**: [`docs/problem-scope.md`](./docs/problem-scope.md)
- **Dual-Documentation Specifications**: [`docs/documentation-model.md`](./docs/documentation-model.md)
- **User Journey & Escalation Protocol**: [`docs/user-journey.md`](./docs/user-journey.md)
- **Team Task Board & Milestones**: [`docs/roadmap.md`](./docs/roadmap.md)

---

## Engineering Rules of Engagement
1. **Safety First**: Adhere strictly to the safety tiers defined in `.agents/rules/safety.md`. Never propose or execute unvalidated administrative commands.
2. **Consult the Roadmap**: Before starting any task, check [`docs/roadmap.md`](./docs/roadmap.md). Respect task ownership assigned to `@Dev1`, `@Dev2`, or `@Dev3`.
3. **Filesystem Over Chat Memory**: Document all architectural decisions, schema changes, and process modifications immediately in `docs/`. Never rely on transient conversation history.
4. **Token & Context Hygiene**: Keep queries focused on individual documents or modules to maximize performance on free model tiers.
