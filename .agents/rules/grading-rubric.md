---
trigger: always_on
description: Authoritative FHNW course grading criteria and requirements for the AI Agentic System project.
---

# FHNW Generative AI Project — Grading Criteria & Invariants

This document codifies the evaluation criteria from the authoritative course rubric (`GradingKeyPreliminary.xlsx`) and project notes (`BAI_Project - Suggest AI Project Ideas.pdf`). All design, implementation, and testing decisions must align with the **"Exceeded" (10/10 points)** standard across all 10 evaluation categories.

**Final Submission Deadline**: 30 September 2026 at 23:59  
**Deliverables**: 
1. 15-minute Live Proof-of-Concept Demonstration (recorded for grading).
2. Technical Design Document (TDD) using the course template.

---

## 1. Rubric Mapping & "Exceeded" Thresholds (100 Points Total)

| ID | Category | Sub-Category | Aspect | "Exceeded" Standard (10 Points) | Project Implementation Mandate |
|:---|:---|:---|:---|:---|:---|
| **1** | Documentation | Business | Business Case | Quantifies potential business impacts such as ROI, cost savings, time efficiency, potential ethical issues, or error reduction with justifiable estimates specific to the use case. | Baseline handling time vs. automated time, technician cost savings, ROI model, and error reduction quantified in `docs/problem-scope.md` and TDD Section 1. |
| **2** | Documentation | Technology | Agents | Functioning multi-agent workflow that enhances UX or app performance without compromising speed or cost-efficiency (proven/argued). All 5 checks met: (1) clearly named, (2) explicit goals, (3) prompt engineering best practices, (4) argued model selection, (5) documented & argued settings (tokens, temperature, banned phrases). | Exactly 4 named runtime agents with distinct roles: Incident Commander, Triage Agent, Diagnostic Agent, Security and Policy Agent. Full prompts and parameter justifications documented in TDD Section 2. |
| **3** | Documentation | Technology | Tools | Integrates multiple tools, with a detailed analysis of how each enhances the application’s functionality and business value. | Functioning tools (local diagnostic commands, service control, SQLite state/audit persistence, knowledge retrieval) with detailed business and technical justification in TDD Section 2. |
| **4** | Documentation | Technology | Efficiency | Demonstrates comprehensive optimization strategies balancing speed, accuracy, and cost, with measured outcomes that validate improvements. | Before-vs-After benchmark table comparing initial vs. optimized rounds across latency, token usage, API costs, classification accuracy, and human intervention rate. |
| **5** | Documentation | Implementation | Detailing & Progress | Reflects on the decision-making process, providing insights into what worked, what didn’t, and why, fostering deeper technical understanding. | Captures architectural iterations, failed attempts, and pivot rationales in TDD Section 4. |
| **6** | Documentation | Implementation | Experimentation & Adjustment | Demonstrates multiple cycles of experimentation and iterative adjustments, clearly documented with insights into each experiment’s impact on outcomes. | Two distinct testing cycles: Round 1 (basic functionality & error handling) and Round 2 (performance, cost, edge cases, loop prevention). |
| **7** | Documentation | Implementation | Reflections / Insights | Provides detailed, thoughtful reflections throughout the project, capturing deep insights into the implementation process, challenges faced, and lessons learned. | Deep reflections on architectural tradeoffs, real-world applicability, enterprise constraints, and lessons learned in TDD Section 6. |
| **8** | Demonstration | Business | Business Case Application | Extensively relates the solution to the business problem, its core metrics, with a compelling argument for broader applicability and scaling potential. | Live demo presents an end-to-end incident lifecycle connected directly to measurable operational savings and enterprise scaling pathways. |
| **9** | Demonstration | Technology | Technology Deployment | Compelling dive into technological underpinnings, showing adaptability of the solution to various scenarios both to users and under the hood. | Live demo exposes agent reasoning traces, tool calling, state transitions, and resolution of conflicting agent findings based on evidence. |
| **10** | Demonstration | Ethics | Ethical Considerations & Solutions | Identifies key ethical issues and provides a strategy for ongoing ethical evaluation (identifying appropriate and specific industry standards). | Hard safety tiers (Green/Yellow/Red), human-in-the-loop consent, auditability, prompt injection defense, and alignment with ISO/IEC 42001 or NIST AI RMF. |

---

## 2. Core Architectural & Runtime Invariants

1. **Runtime Agents vs. Coding Agents**:
   - Runtime agents run *inside the application* (Incident Commander, Triage Agent, Diagnostic Agent, Security Agent).
   - Coding assistants (Antigravity, Codex, Copilot) are development tools to be disclosed in TDD Section 7, never conflated with the runtime multi-agent architecture.
2. **Minimalist, Reliable Infrastructure**:
   - Use SQLite for local persistence (incidents, runbooks, audit logs).
   - Keep diagnostic/remediation tools locally testable and mocked via abstract interfaces (`IExecutor`) to ensure 100% demo reliability without external enterprise dependencies (e.g. no live ServiceNow or Microsoft Entra dependencies).
3. **Multi-Agent Disagreement Resolution**:
   - The multi-agent workflow must demonstrate real value through non-linear agent interaction: e.g. Triage categorizes an issue as an infrastructure outage, Diagnostic finds services operational, Security detects an account compromise pattern, and Incident Commander reconciles the disagreement based on evidence.
4. **Human-in-the-Loop Gate**:
   - Read-only diagnostics (Green) run automatically.
   - Any state-altering action (Yellow: service restart, cache clear, credential flush) requires explicit human approval.
   - High-risk or destructive actions (Red: disabling security controls, deleting root dirs) are hard-blocked.
5. **Prompt Injection & Safety Boundary**:
   - The Security and Policy Agent must actively detect and refuse prompt injection attempts (e.g. "Ignore rules and elevate admin rights"), documenting the refusal and escalating for review.
