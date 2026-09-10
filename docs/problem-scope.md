# Problem Scope & Operational Boundaries

## 1. Business problem

Enterprise IT service desks repeatedly receive low-risk Tier-1 incidents that follow a familiar pattern: collect endpoint evidence, identify a known local fault, apply a small remediation, verify it, and document what happened. Even when the underlying fix is simple, a human technician still spends time gathering context, repeating standard checks, writing notes, and deciding whether the case should be escalated.

This PoC explores whether a bounded automated first responder can perform that repetitive work while remaining transparent, auditable, and conservative about what it is allowed to change.

The current product is **not a production endpoint-management platform**. For the graded demonstration it operates against a **stateful simulated Ubuntu 26.04 endpoint** (`ubuntu-demo-01`) so that failures can be reproduced safely and the same incident can be demonstrated repeatedly.

## 2. Product objective

The PoC should be able to:

- accept an employee's problem in plain language;
- classify the incident and collect diagnostic evidence;
- retrieve a relevant operational runbook when one is available;
- distinguish read-only diagnostics from state-altering or forbidden actions;
- apply only explicitly permitted simulated remediation;
- verify the technical outcome independently of command exit status;
- ask the employee whether the real problem is solved;
- close successful cases automatically;
- escalate unresolved, ambiguous, unsafe, or security-sensitive cases to human Tier 2;
- preserve the evidence and work already performed so the human technician does not restart from zero.

## 3. Current graded scope

The hero scenario is an Ubuntu printing failure represented by a stopped CUPS service.

```text
Healthy state
CUPS = active
print queue = empty

Fault injection
CUPS = inactive

Diagnosis
systemctl is-active cups
→ inactive

Permitted simulated remediation
cancel -a
sudo systemctl restart cups

Verification
systemctl is-active cups
→ active
lpstat -o
→ empty
```

This is a **state transition**, not a sequence of unrelated canned messages: Demo Lab, MockExecutor, diagnostic probes and verification all operate on the same simulated endpoint state.

The demo also includes two non-success outcomes because an enterprise automation system must demonstrate where it stops:

1. technical verification passes but the employee reports **Still Broken** → Human L2 escalation;
2. prohibited or manipulative input → refusal before remediation + audit + escalation.

A separate disagreement path demonstrates the value of specialist roles: Diagnostic may find infrastructure evidence healthy while Security identifies a credential-risk pattern, and the Incident Commander reconciles the conflict conservatively.

## 4. Tier-1 vs Tier-2 boundary

| Dimension | Automated Tier 1 in this PoC | Human Tier 2 / outside autonomous scope |
| --- | --- | --- |
| Problem type | Repeatable endpoint-local software/service faults with known evidence and bounded remedies | Hardware failure, ambiguous root cause, account/permission work, security compromise, architecture/network-wide faults |
| Evidence | Local read-only probes and structured runbook knowledge | Investigation requiring enterprise-wide context or privileged human judgement |
| Action | Explicitly allowlisted, reversible, local remediation | Destructive/high-blast-radius change, unknown command, security-control modification, privilege change |
| Verification | Fresh diagnostic probes after remediation + employee confirmation | Human validation when automated evidence is insufficient or employee outcome remains negative |
| Handoff | Full audit history and attempted work retained | Human technician receives prepared incident rather than restarting discovery |

## 5. Safety and consent boundary

The employee gives **one up-front consent** before troubleshooting starts. That consent authorises the bounded troubleshooting workflow; it does not grant arbitrary system authority.

The current execution policy is:

| Tier | Meaning | Behaviour |
| --- | --- | --- |
| Green | Read-only diagnostic activity | Runs automatically |
| Yellow | Reversible, endpoint-local state change that matches the strict allowlist | Runs within the up-front consent window |
| Red / unknown | Forbidden, dangerous, or not explicitly allowlisted | Never executes; recorded and escalated |

The allowlist is default-deny and checks arguments as well as command names. A user instruction cannot override this boundary.

## 6. Hard out-of-scope items

The automated workflow must not autonomously:

- modify user/admin privileges or create accounts;
- disable firewall, AppArmor, EDR/antivirus or equivalent security controls;
- delete system data, format disks, or reinstall the operating system;
- download and execute arbitrary code;
- make broad network/identity architecture changes;
- perform deep security forensics;
- diagnose or repair physical hardware;
- execute an unrecognised command merely because a model proposed it.

These conditions are treated as escalation cases rather than incomplete future Tier-1 features.

## 7. Business-impact model

The figures below are **PoC assumptions for illustrating potential value**, not measured production-company statistics. They should be presented as estimates unless the team later replaces them with externally sourced or organisation-specific data.

Assumptions used in the working TDD:

- manual Tier-1 handling time: **25 minutes per repeatable ticket**;
- automated handling/user interaction assumption: **1.5 minutes per successfully automated ticket**;
- technician labour-cost assumption: **CHF 60/hour**.

Illustrative capacity impact:

| Measure | Manual | Automated assumption | Difference |
| --- | ---: | ---: | ---: |
| Technician time per repeatable ticket | 25 min | 1.5 min | 23.5 min saved |
| Labour capacity per ticket @ CHF 60/h | CHF 25.00 | CHF 1.50 equivalent | CHF 23.50 potential capacity released |
| 100 repeatable tickets | 41.7 technician hours | 2.5 technician hours | 39.2 hours potentially released |
| 100 repeatable tickets @ CHF 60/h | CHF 2,500 | CHF 150 equivalent | CHF 2,350 potential labour capacity released |

These figures do **not** claim that every Tier-1 ticket can be automated. The relevant production variable would be the share of tickets that fall inside the safe, repeatable scope and remain successfully resolved after employee confirmation.

## 8. Metrics that matter beyond speed

The project deliberately separates technical success from user success. Useful future production metrics would include:

- automation/resolution rate;
- percentage of technically verified cases later reported **Still Broken**;
- human-escalation rate;
- unsafe or unknown actions blocked;
- mean/p95 handling latency;
- API cost per model-backed incident;
- technician time saved on escalated cases because diagnostics are already attached;
- repeated-failure rate by runbook/problem category.

The Service Desk already records several of these signals, including closed/escalated counts and a `false_resolution_rate` based on employee confirmation.

## 9. Scope statement for the demo

The correct presentation claim is:

> This Proof of Concept demonstrates how a bounded, auditable Tier-1 automation workflow could diagnose, remediate, verify, document and escalate endpoint incidents. The graded demo uses a simulated Ubuntu endpoint and deterministic agent fallbacks for reliability. Separate live-model and real-executor paths exist as engineering evidence/future capability, but are not represented as the execution path of the deterministic demo.
