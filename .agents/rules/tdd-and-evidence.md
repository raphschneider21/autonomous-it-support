---
trigger: always_on
description: Guidelines for compiling the Technical Design Document (TDD) and gathering continuous development evidence.
---

# Technical Design Document (TDD) & Evidence Standards

The Technical Design Document must follow the structure defined in `Generative AI Solution Technical Description Documentation Template v1.docx`. 

> [!IMPORTANT]
> **Capture Evidence During Development**: Screenshots, failed test runs, latency measurements, and prompt adjustments must be captured in real time. Do not attempt to reconstruct experiments after development is completed.

---

## 1. Document Structure & Content Guidelines

### Section 1: Business Case
- **1a. Description**: Define the business context, affected users/organization, and specific enterprise IT support problems addressed.
- **1b. Evidence**: Include initial concept notes, whiteboard sketches, or concept maps (e.g. system diagrams or photos with brief explanatory notes).
- **1c. Reflections**: Quantify potential business impact: baseline incident handling time (e.g. 20-30 min) vs. automated triage/resolution (<2 min), technician labor cost savings, error reduction rate, and justifiable ROI estimates.

### Section 2: Initial Setup
- **2a. Agent & Tools Configuration**: High-level description of the 4 runtime agents and toolset.
- **2b. Evidence**: Screenshots of agent configurations, prompt definitions, and tool schemas where parameters (token limits, temperature, tool declarations) are clearly legible.
- **2c. Reflection**: Justify agent roles, model selections (e.g. lightweight vs. reasoning models), and tool integrations against project goals.

### Section 3: Initial Testing & Improvement Planning
- **3a. First Round of Testing**: Describe the baseline test suite covering realistic scenarios and edge cases (unusual errors, prompt injections, infinite loop hazards). Maintain a test suite repository (`tests/test_suite.json`).
- **3b. Evidence**: Screenshots and logs of test inputs and outputs showing both successful resolutions and failed/edge attempts.
- **3c. Insights**: Discuss initial failures, misclassifications, latency bottlenecks, and lessons learned.

### Section 4: Major Changes & Iteration
- **4a. Adjustments Made**: Document major architectural or prompt improvements resulting from initial test findings. Include in-line attribution for feedback from peers and visiting experts (e.g. "Following peer review on 2026-09-15...").
- **4b. Evidence**: Screenshots of updated code, prompt revisions, and architectural adjustments.
- **4c. Reflection**: Explain the rationale behind major changes and how they enhanced accuracy, safety, or efficiency.

### Section 5: Second Testing & Evaluation
- **5a. Second Round of Testing**: Run the refined test suite with an emphasis on latency, token costs, edge case robustness, and safety guardrails.
- **5b. Evidence**: Comparative test logs and screenshots demonstrating improvements over Round 1.
- **5c. Insights**: Quantify improvements in accuracy, response time, and reliability.

### Section 6: Conclusion & Reflections
- **6a. Project Wrap-Up**: Concise summary of the final PoC state and real-world effectiveness.
- **6b. Evidence**: Final workflow screenshots, end-to-end execution timing, and complete incident lifecycle logs.
- **6c. Reflection / Insights**: Reflect on initial plan vs. final achievement, ethical resolutions, key technical learnings, and potential for production scaling.

### Section 7: Disclosure of AI Interactions
- Transparent disclosure of AI tools used during development (e.g. Antigravity IDE, Claude, Codex) for planning, coding, test generation, and documentation drafting.
- Document human review processes, validation steps, and control mechanisms ensuring code safety and security.

### Section 8: References
- Formal references as necessary. (Note: Standard SDK documentation, Vertex AI docs, and company operational details do not require citation. Peer/expert feedback must be cited in-line).

---

## 2. Formatting & Visual Evidence Standards
1. **Consistent Screenshot Sizing**: Keep screenshot dimensions and aspect ratios consistent for a clean layout.
2. **Tabular Metrics**: Present performance data in structured tables (Initial Round vs. Final Round).
3. **Traceability**: All claims of accuracy or speed improvements must link back to stored test suite runs or recorded logs.
