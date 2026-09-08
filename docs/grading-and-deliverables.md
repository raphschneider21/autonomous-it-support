# Academic Deliverables & Grading Rubric Mapping

This repository hosts the **Autonomous Enterprise IT Support Agent (Tier 1)** project developed for the FHNW Generative AI module.

- **Final Submission Deadline**: 30 September 2026 at 23:59
- **Deliverables**:
  1. 15-minute Live Proof-of-Concept Demonstration (Recorded)
  2. Technical Design Document (TDD) using the official course template

---

## 1. Ten Grading Criteria & Compliance Matrix

| Rubric ID | Assessment Area | Required Standard ("Exceeded" / 10 Points) | Repository Implementation & Evidence Location |
|:---|:---|:---|:---|
| **1. Business Case** | Documentation | Quantified business impact: baseline incident handling time, labor cost savings, error reduction rate, justifiable ROI estimates. | [`docs/problem-scope.md`](./problem-scope.md), TDD Section 1 |
| **2. Agents** | Documentation | Functioning multi-agent workflow; 5 criteria met: named agents, clear goals, best-practice instructions, argued model selection, documented settings. | [`docs/user-journey.md`](./user-journey.md), [`.agents/rules/grading-rubric.md`](../.agents/rules/grading-rubric.md), TDD Section 2 |
| **3. Tools** | Documentation | Multiple functioning tools (diagnostics, service control, local SQLite persistence, knowledge retrieval) with business value analysis. | [`docs/documentation-model.md`](./documentation-model.md), TDD Section 2 |
| **4. Efficiency** | Documentation | Optimization strategy balancing speed, accuracy, and cost with empirical before-vs-after measured outcomes. | Benchmark logs in `tests/`, TDD Section 5 & 6 |
| **5. Detailing & Progress** | Documentation | Rationale behind major architectural decisions, documenting what worked, what failed, and key learnings. | Commit history, TDD Section 4 |
| **6. Experimentation** | Documentation | Multiple cycles of experimentation and iterative adjustments, testing realistic and edge cases. | Test suites in `tests/`, TDD Section 3 & 5 |
| **7. Reflections** | Documentation | Thoughtful reflections on implementation, challenges, ethical resolutions, and future scaling potential. | TDD Section 6 |
| **8. Business Demo** | Demonstration | 15-minute live demo showing an end-to-end incident lifecycle connected to operational savings. | [`.agents/rules/live-demo-spec.md`](../.agents/rules/live-demo-spec.md) |
| **9. Technology Demo** | Demonstration | Under-the-hood inspection of agent traces, tool calls, state changes, and evidence-based disagreement resolution. | [`.agents/rules/live-demo-spec.md`](../.agents/rules/live-demo-spec.md) |
| **10. Ethics & Safety** | Demonstration | Explicit safety tiers, human consent gates, prompt injection guardrails, audit logging, and ongoing evaluation standards. | [`.agents/rules/safety.md`](../.agents/rules/safety.md), TDD Section 1 & 6 |

---

## 2. Living Documentation Index

| File | Purpose & Role |
|:---|:---|
| [`GEMINI.md`](../GEMINI.md) | AI Agent entrypoint and operational rules of engagement |
| [`docs/problem-scope.md`](./problem-scope.md) | Business problem definition, scope boundaries, and high-frequency incident taxonomy |
| [`docs/documentation-model.md`](./documentation-model.md) | Specifications for AI-Executable Runbooks (YAML) and Human Incident Reports (Markdown) |
| [`docs/user-journey.md`](./user-journey.md) | Sequence diagrams and end-to-end human-in-the-loop escalation flows |
| [`docs/roadmap.md`](./roadmap.md) | Task tracking across `@Dev1`, `@Dev2`, and `@Dev3` mapped against course milestones |
| [`.agents/rules/grading-rubric.md`](../.agents/rules/grading-rubric.md) | Strict rubric requirements and invariants for all agentic workflows |
| [`.agents/rules/tdd-and-evidence.md`](../.agents/rules/tdd-and-evidence.md) | TDD authoring standards and real-time evidence capture protocol |
| [`.agents/rules/live-demo-spec.md`](../.agents/rules/live-demo-spec.md) | 15-minute live demonstration cadence and under-the-hood inspection script |
| [`.agents/rules/safety.md`](../.agents/rules/safety.md) | Green/Yellow/Red command execution safety boundaries |
| [`.agents/rules/architecture.md`](../.agents/rules/architecture.md) | Decoupled 4-subsystem modular boundaries |
| [`.agents/rules/team-conventions.md`](../.agents/rules/team-conventions.md) | Git workflow and token optimization conventions |
