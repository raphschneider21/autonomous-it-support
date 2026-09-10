# Final Demo Plan — Autonomous IT Support PoC

**Status:** FROZEN DEMO SKELETON  
**Purpose:** Authoritative source of truth for the final 15-minute FHNW Proof-of-Concept demonstration.  
**Submission deadline:** 30 September 2026, 23:59

This document defines the demo we are actually building and presenting. Developer workstreams, AI-assistant prompts, UI refinements, test plans, rehearsal scripts, and the final TDD must align with this plan unless the team explicitly approves a change to the frozen skeleton.

---

## 1. What the final demo is

The final submission demonstrates a polished **enterprise IT-support Proof of Concept** in which an automated Tier-1 support system can:

- accept a user's IT problem in plain language;
- inspect a simulated Ubuntu endpoint;
- classify and diagnose the incident;
- use machine-readable operational knowledge/runbooks;
- execute only policy-permitted simulated remediation;
- verify the technical result;
- ask the employee whether the real problem is resolved;
- close successfully resolved incidents;
- escalate unresolved, unsafe, or security-sensitive incidents to human Tier-2 support;
- preserve the diagnostic history and actions already taken;
- expose the process to IT staff through an auditable service-desk view.

The demo is intentionally designed as a **deterministic, mock-backed PoC**. Reliability, reproducibility, safety demonstration, and a clear end-to-end story are more important for the final presentation than running a frontier model or issuing real repair commands against the Ubuntu host.

The repository may contain optional real-model and real-executor capabilities. Those capabilities are **not the required execution path for the graded demo** and must not be enabled accidentally during the presentation.

### Demo truth rule

The presentation must never imply that a simulated action was a real operating-system repair or that deterministic fallback behaviour was live generative-model reasoning.

The correct framing is:

> For the PoC, endpoint execution and the demonstrated agent path are kept deterministic so the team can reproduce scenarios, test safety behaviour, and deliver a reliable live demonstration. The architecture separates those interfaces so more capable model and executor implementations can be evaluated later without redesigning the user, ticketing, or audit workflow.

---

## 2. Frozen decisions

The following six decisions are approved and define the demo skeleton.

1. **Physical topology:** The Ubuntu VM represents the employee endpoint; the Mac represents central IT and hosts the Service Desk.
2. **Primary successful scenario:** A simple Ubuntu printing/CUPS incident is the hero resolution scenario.
3. **Escalation scenario:** A technically successful action can still be escalated when the employee reports that the real problem remains. The ticket moves from automated Tier 1 to human Tier 2 with the complete history attached.
4. **Multi-agent disagreement:** The disagreement/reconciliation moment is embedded in the escalation/security portion of the demo rather than becoming a separate long scenario.
5. **Under-the-hood presentation:** A polished Live Operations view inside the Service Desk is the primary technical trace shown to the audience. A raw terminal remains optional backup evidence, not the main presentation surface.
6. **Demo transparency:** The presentation explicitly identifies endpoint execution/model behaviour as deterministic/mock-backed for PoC reliability.

These decisions should not be redesigned independently inside a developer workstream.

---

## 3. Physical demo architecture

```text
EMPLOYEE WORKSTATION — Ubuntu VM
│
├── Employee Support UI
│   └── report problem / consent / progress / result / user confirmation
│
├── Demo Lab
│   └── presenter-only fault injection and reset controls
│
├── Troubleshooter / Incident Engine
│   └── deterministic demo path
│
├── MockExecutor + Ubuntu simulated endpoint state
│   └── diagnostics / remediation / verification without damaging the host VM
│
└──────────── HTTP ───────────────────────────────►

CENTRAL IT — Mac
│
└── Service Desk
    ├── ticket queue
    ├── ticket detail
    ├── automated L1 → human L2 ownership
    ├── timeline / attempted actions
    ├── diagnostics and audit evidence
    ├── documentation / runbook information
    ├── escalation payload
    └── Live Operations technical view
```

### Why this topology is frozen

The audience can immediately understand the enterprise separation:

- **Ubuntu VM:** what the employee experiences;
- **Mac:** what central IT sees;
- **HTTP handoff:** how the endpoint reports incidents and escalation information to IT.

The mock executor prevents the demo application from damaging or depending on the same operating-system services that host the presentation.

No additional VM, cloud platform, ServiceNow/Jira instance, or external enterprise dependency is required for the final PoC.

---

## 4. Demo execution mode

The final demo must have an explicit configuration that makes its execution mode unambiguous. Exact variable names may follow the implemented configuration layer, but the resulting state must be equivalent to:

```text
DEMO_MODE=1
EXECUTOR=mock
AGENT_MODE=deterministic/fallback
MONITORING=enabled
MONITORING_URL=<Mac Service Desk address>
```

The running system should expose enough status information that the presenter can confirm before recording:

```text
Endpoint: ubuntu-demo-01
Executor: Simulated / Mock
Agent mode: Deterministic PoC
Service Desk: Connected
```

The normal demo launcher must **not automatically pull from GitHub**. Recording/rehearsal uses a known-good frozen commit. Repository updates are a separate deliberate action.

---

## 5. Presentation surfaces

### 5.1 Employee Support — Ubuntu VM

**Audience question answered:** "What does the employee experience?"

This is the simplest interface in the system. It must not expose engineering noise that an ordinary employee would not understand.

The core user journey is:

```text
Describe problem
    ↓
Understand and accept troubleshooting scope
    ↓
Automated investigation
    ↓
Outcome
    ↓
"Did this solve your problem?"
    ↓
Yes → close ticket
No  → escalate to Tier 2
```

The employee view should show concise plain-English progress rather than raw agent/tool traces.

The consent view should make clear that troubleshooting is authorised but not unrestricted. The system may run only actions permitted by its safety policy, and unsafe/unrecognised actions remain blocked even after the user consents.

The successful result should make the payoff obvious: what was found, what was done, whether technical verification passed, and the incident/ticket identifier.

---

### 5.2 Demo Lab — Ubuntu VM

**Audience question answered:** "How can the team reproducibly create a broken endpoint for the live demonstration?"

Demo Lab is a presenter/tester surface, not an employee feature. It controls simulated Ubuntu endpoint state used by the MockExecutor.

Expected shape:

```text
UBUNTU ENDPOINT LAB

Endpoint: ubuntu-demo-01

Printing        Healthy      [ Inject CUPS failure ]
DNS             Healthy      [ Inject DNS failure ]
Storage         Healthy      [ Simulate disk issue ]
Audio           Healthy      [ Inject audio issue ]
...

[ RESET ENDPOINT ]
```

The final set of faults may be limited to the scenarios needed by the presentation. Breadth is less important than making the selected scenarios deterministic and convincing.

#### Stateful simulation requirement

The mock should model state rather than only replay canned strings.

Example:

```text
Demo Lab injects fault:
CUPS = inactive

Agent diagnostic:
systemctl is-active cups
→ inactive

Simulated remediation:
systemctl restart cups
→ success

Endpoint state changes:
CUPS = active

Verification:
systemctl is-active cups
→ active
```

The diagnosis/remediation/verification lifecycle therefore represents real application state transitions even though the endpoint is simulated.

---

### 5.3 Service Desk — Mac

**Audience question answered:** "What does the IT technician see?"

The existing monitoring/service-desk application is the basis. It should be refined rather than replaced.

The ticket queue must make support ownership immediately visible. Example:

```text
INC-1042    Printing    AUTOMATED L1    RESOLVED
INC-1043    Security    HUMAN L2        ESCALATED
INC-1044    Network     AUTOMATED L1    INVESTIGATING
```

Escalation should have a visually obvious ownership transition:

```text
AUTOMATED L1
     ↓
 HUMAN L2
```

The ticket detail is the central evidence view. Recommended information architecture:

```text
Overview | Timeline | Diagnostics | Documentation | Escalation
```

#### Overview

Show the employee report, endpoint, category/severity, current status, current owner/support level, runbook match where applicable, final assessment, and resolution state.

#### Timeline

Show the chronological lifecycle of the incident, including creation, triage, diagnostics, safety decisions, remediation attempts, verification, user confirmation, closure, or escalation.

#### Diagnostics

Show tool/command activity and relevant outputs in a readable way.

#### Documentation

Present both forms of operational documentation without misrepresenting where they came from:

- **Operational runbook:** machine-readable knowledge consumed by the system to diagnose/remediate a known problem.
- **Incident report:** human-readable documentation generated from this specific execution.

The runbook should not be described as newly generated after the incident if it already existed and was used to solve the incident.

#### Escalation

For Tier-2 handoff, show the structured escalation information and everything already attempted so a human technician does not have to repeat Tier-1 discovery work.

---

### 5.4 Live Operations — inside the Service Desk

**Audience question answered:** "What is the system actually doing under the hood?"

Live Operations is the primary technical presentation surface. It should use large, readable, terminal-inspired styling while remaining a purpose-built UI rather than an uncontrolled raw shell/log window.

Example presentation:

```text
LIVE OPERATIONS                              INC-1042
Endpoint: ubuntu-demo-01
Mode: SIMULATED ENDPOINT
Status: INVESTIGATING

09:42:11.104  SECURITY
               Input policy check                     PASS

09:42:11.119  TRIAGE
               category: printing
               severity: medium

09:42:11.128  DIAGNOSTIC
               $ systemctl is-active cups
               → inactive

09:42:11.139  KNOWLEDGE
               matched: cups-service-recovery
               confidence: 93%

09:42:11.150  EXECUTOR
               $ systemctl restart cups
               → permitted by policy

09:42:11.162  VERIFY
               $ systemctl is-active cups
               → active

09:42:11.170  COMMANDER
               TECHNICAL VERIFICATION PASSED
```

The view should be driven by actual incident/audit data where possible. The audience should be able to see agent/component identity, evidence, tool calls, safety decisions, state transitions, and verification without needing to read source code.

A raw terminal or source-code window may be retained as backup/deeper evidence if requested, but it is not the main demo experience.

---

## 6. Canonical demo scenarios

The final 15-minute presentation is organised around three memorable outcomes rather than a checklist of disconnected technical features.

### Scenario A — "It solves something"

**Hero scenario:** Ubuntu CUPS/printing failure.

1. Presenter briefly shows the healthy simulated endpoint in Demo Lab.
2. Presenter injects the CUPS/printing failure.
3. Employee reports that printing is not working.
4. Troubleshooter investigates the simulated endpoint.
5. Live Operations exposes classification, diagnostics, runbook retrieval, policy decision, remediation, and verification.
6. Simulated remediation changes the endpoint state from broken to healthy.
7. Technical verification passes.
8. Employee confirms the real problem is solved.
9. Service Desk shows the ticket closed automatically with its complete history and documentation.

**Audience takeaway:** Routine Tier-1 work can be resolved automatically while remaining visible and auditable to IT.

---

### Scenario B — "It knows when to hand over"

The second act demonstrates that technical success and user success are not the same thing.

1. The automated system investigates and performs a permitted action.
2. Its technical verification passes.
3. The employee reports **Still Broken**.
4. The ticket changes ownership from **Automated L1** to **Human L2**.
5. On the Service Desk, the Tier-2 technician receives the original complaint plus diagnostics, actions already attempted, outputs, verification result, user verdict, and generated incident report.

Where appropriate within this scenario/security context, show a concise multi-agent disagreement:

```text
Diagnostic Agent:
Endpoint behaviour appears technically healthy.

Security Agent:
Observed/reported behaviour is security-sensitive or inconsistent with an ordinary infrastructure fault.

Incident Commander:
Prefer the security interpretation and stop ordinary automated remediation / escalate.
```

The disagreement must be tied to actual evidence in the demonstrated flow rather than presented as four agents arguing for theatrical effect.

**Audience takeaway:** Failure of automation is not wasted work. It converts an unstructured employee complaint into a prepared Tier-2 case.

---

### Scenario C — "It refuses something"

Use a malicious or policy-violating input such as an attempt to bypass security controls or gain administrative privileges.

1. Employee/malicious input reaches the troubleshooting surface.
2. Safety/input policy identifies the prohibited request.
3. No remediation command executes.
4. The event is audited and escalated/reported to the Service Desk.
5. Live Operations and/or ticket detail clearly show the refusal.

**Audience takeaway:** User consent and automation do not provide unlimited authority. Unsafe actions remain outside the permitted execution boundary.

---

## 7. 15-minute presentation skeleton

The exact narration will be written and rehearsed later, but the presentation should follow this story rather than the older rubric-by-rubric sequence.

| Time | Beat | Primary surface | Purpose |
|---:|---|---|---|
| 0:00–0:45 | Business problem | Employee / brief framing | Establish repetitive Tier-1 support cost/friction |
| 0:45–1:15 | Product proposition | Employee Support | Show how simple the employee interaction is |
| 1:15–3:30 | Hero diagnosis | Employee + Live Operations | Demonstrate investigation and technical visibility |
| 3:30–5:15 | Remediation + verification | Live Operations + Employee | Deliver first payoff |
| 5:15–6:30 | Ticket closes | Service Desk | Show audit/history/documentation and automated L1 value |
| 6:30–6:50 | Second-act transition | Presenter | "That was the easy case. What happens when automation should stop?" |
| 6:50–9:30 | Escalation / disagreement | Employee + Live Operations | Show limits, evidence, and multi-agent value |
| 9:30–10:30 | L1 → L2 handoff | Service Desk | Show everything the human technician inherits |
| 10:30–11:30 | Attack / prohibited request | Employee + Live Operations | Safety/ethics moment |
| 11:30–12:15 | Refusal appears in IT | Service Desk | Show auditability and policy boundary |
| 12:15–13:30 | Technical proof | Live Operations / curated implementation evidence | Explain architecture, contracts, tools and mock boundary |
| 13:30–14:15 | Experimentation / measured outcomes | Service Desk / evidence view | Show authentic measurements and iteration |
| 14:15–15:00 | Business close + limitations | Presenter / final product view | Connect PoC to value, scaling potential and honest limitations |

The three memorable outcomes are:

> **It fixes something.**  
> **It knows when to hand over.**  
> **It refuses something.**

---

## 8. Demo launcher and reliability requirements

There should ultimately be two normal launch paths.

### Ubuntu — Demo Endpoint launcher

The launcher should:

- start/check the Troubleshooter service;
- force the approved demo/mock configuration;
- initialise/reset the simulated endpoint state;
- point monitoring at the Mac Service Desk;
- check service health/connectivity;
- open the Employee Support UI;
- make Demo Lab easy to open.

### Mac — Service Desk launcher

The launcher should:

- start/check the monitoring/service-desk service;
- initialise/check its database;
- expose a deliberate demo reset option;
- open the Service Desk.

### Reliability principles

- Normal demo launch does not run `git pull`.
- Rehearsal and recording use one known-good commit.
- Reset behaviour is deterministic.
- Demo data reset must not delete committed benchmark/evidence artifacts.
- A service-desk communication failure must not crash endpoint troubleshooting.
- The demo should have a preflight/readiness gate before recording.
- Every canonical scenario should have automated regression coverage where practical.

---

## 9. Product boundaries / non-goals for the final demo

Unless a frozen decision is changed deliberately, the following are **not** required before the final demonstration:

- production deployment;
- real enterprise endpoint fleet management;
- real ServiceNow/Jira integration;
- cloud hosting;
- additional VMs;
- arbitrary autonomous repair of unknown computers;
- running destructive faults against the host Ubuntu VM;
- enabling `EXECUTOR=real` for presentation spectacle;
- depending on a live external LLM/API during the graded demo;
- broad feature expansion unrelated to the three canonical scenarios.

Existing experimental capabilities may remain in the repository as future-work evidence, but they must not make the final demo less reliable or less truthful.

---

## 10. Shared interface contracts for later workstreams

The detailed three-developer split will be defined separately. Until then, all future work should preserve these integration boundaries.

### Employee / Incident Engine contract

The employee surface needs to be able to:

- submit a problem;
- receive understandable progress/state;
- receive a final technical result;
- submit the user's `solved` / `still broken` verdict;
- display the incident identifier and escalation/closure outcome.

### Demo Lab / MockExecutor contract

Demo Lab needs to be able to:

- read simulated endpoint health/state;
- inject only approved demo faults;
- reset to a known healthy baseline;
- cause diagnostics to observe the injected state;
- allow simulated remediation to mutate that state;
- allow verification to observe the post-remediation state.

### Incident Engine / Service Desk contract

The endpoint needs to report enough structured information for the Service Desk to show:

- incident identity and endpoint;
- user report;
- category/severity/status;
- support ownership level;
- agent/component activity;
- commands/tools and relevant outputs;
- runbook used where applicable;
- safety/refusal events;
- technical verification;
- user confirmation;
- generated incident report/documentation references;
- escalation payload and attempted work.

### Service Desk / Live Operations contract

Live Operations should reuse real incident/audit information rather than inventing a second incompatible trace format. Presentation-specific formatting is allowed; contradictory duplicate state is not.

---

## 11. Change control

This document is the frozen demo skeleton.

A developer or AI assistant may freely improve implementation details, visual design, test quality, accessibility, performance, and code structure **inside an assigned workstream** as long as the behaviour remains compatible with this plan.

Changes that affect any of the following must be brought back to the demo/product owner before implementation:

- physical topology;
- canonical scenarios;
- mock-vs-real execution policy;
- employee/ticket ownership lifecycle;
- L1 → L2 semantics;
- safety/consent model;
- shared API/data contracts;
- the 15-minute narrative structure;
- addition/removal of a primary presentation surface.

The purpose is not bureaucracy. It is to stop three developers and three AI assistants from independently redesigning the same demo in incompatible directions.

---

## 12. Next project step

With this skeleton frozen, the next task is to divide the remaining implementation and polish into three independent developer workstreams.

Each developer will receive:

1. a short human-readable brief explaining their responsibility and definition of done; and
2. a tailored AI bootstrap prompt instructing their AI assistant to read this document, read the developer-specific workstream contract, inspect the repository, stay inside the assigned ownership boundary, implement/test iteratively, and guide the human appropriately.

The least experienced developer's AI prompt must assume no prior command-line or software-development tooling knowledge and provide explicit, copyable, step-by-step operational guidance without being patronising.

---

**Frozen skeleton approved by the team on 10 September 2026.**
