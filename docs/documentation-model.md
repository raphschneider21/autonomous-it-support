# Operational Runbooks and Human Incident Reports

## 1. Why the project separates the two

The PoC uses two different forms of documentation with different trust and lifecycle properties:

```text
Operational runbook
= pre-existing, machine-readable knowledge that may guide a known remediation

Incident report
= human-readable documentation generated from one specific execution
```

This distinction is important for both safety and demo truthfulness.

The current runtime **does not claim to generate and promote a new executable runbook automatically after solving an incident**. `RB-CUPS-001` and other runbooks are pre-existing reviewed knowledge. The incident report is the artifact generated from the current case.

A future ingestion/authoring workflow for turning institutional knowledge into reviewed runbooks is described separately in `docs/rag-ingestion-strategy.md` and includes a human review gate before a candidate becomes executable knowledge.

## 2. Operational runbook

Runbooks are YAML documents loaded from the selected runbook store. The graded path uses:

```text
RUNBOOK_STORE=ubuntu-26.04
```

A runbook captures:

- stable identifier/title;
- target OS/environment metadata;
- symptoms/signatures used for retrieval;
- read-only pre-checks;
- ordered remediation steps;
- post-remediation verification;
- rollback guidance where supplied;
- optional parameters/provenance fields.

Representative schema:

```yaml
schema_version: "1.1"
runbook_id: "RB-CUPS-001"
title: "Print Queue Stuck and Nothing Prints (CUPS Backlogged)"
target_os: "ubuntu_26_04"
environment: "vm-safe"
tags: ["printer", "printing", "queue", "cups", "stuck"]

trigger_signatures:
  symptoms:
    - "Print jobs are stuck in the queue and nothing prints"

pre_checks:
  - id: "check_cups_state"
    command: "systemctl is-active cups"
    expected_output_regex: "active|inactive|failed"

remediation_steps:
  - step: 1
    description: "Cancel every queued print job"
    command: "cancel -a"
    elevation_required: false
  - step: 2
    description: "Restart the CUPS printing service"
    command: "sudo systemctl restart cups"
    elevation_required: true

verification:
  - command: "systemctl is-active cups"
    expected_output_regex: "^active"
  - command: "lpstat -o"
    expected_output_regex: "^$"
```

### Runtime safety relationship

A runbook is not a bypass around execution policy.

- pre-checks and verification must be read-only;
- remediation commands must still pass the runtime safety validator;
- placeholders/parameters must be resolved and revalidated;
- Red/unknown commands never execute;
- Yellow classification means local/reversible state change and does **not** imply a current per-command approval modal;
- the graded workflow executes allowlisted Yellow actions only inside the employee's accepted up-front troubleshooting scope.

## 3. Hero runbook: `RB-CUPS-001`

The CUPS scenario is designed for the simulated Ubuntu endpoint.

Expected causal lifecycle:

```text
Demo Lab injects cups_stopped
→ shared state reports CUPS inactive
→ pre-check/diagnostic observes inactive
→ runbook remediation runs through MockExecutor
→ shared state becomes active and queue empty
→ fresh verification observes the new state
```

The Mac host is not modified during the graded demo.

The fact that the runbook targets Ubuntu commands remains useful: the simulation represents the command/evidence contract that a real endpoint adapter could implement later.

## 4. Human-readable incident report

The incident report describes what happened in one execution so a technician can understand the case without reconstructing it from raw database rows.

Useful content includes:

```markdown
# Incident Resolution Report: INC-XXXXXXXX

- Timestamp
- Simulated endpoint
- Original employee prompt

## Root Cause / Assessment
What the system concluded from the available evidence.

## Actions Taken
Chronological diagnostic, policy, remediation and verification evidence.

## Verification & Employee Outcome
- Technical verification: passed/failed
- Employee confirmation: solved/still_broken/not applicable
- Operational runbook used: RB-...
- Final support status: closed or escalated
```

The report should distinguish:

- **technical verification** from **employee confirmation**;
- **pre-existing runbook used** from **incident report generated**;
- **deterministic/mock evidence** from any live-model evidence.

## 5. Scenario A documentation

For the hero CUPS success, Service Desk/incident documentation should make this sequence understandable:

```text
Employee: printer is not printing
Diagnostic evidence: CUPS inactive
Operational knowledge: RB-CUPS-001
Permitted simulated actions: clear queue + restart CUPS
Verification: CUPS active, queue empty
Employee verdict: solved
Final status: closed
```

## 6. Scenario B documentation

When technical verification passes but the employee selects **Still Broken**, the generated documentation becomes Human-L2 handoff evidence.

The technician should receive:

- original report;
- category/severity;
- diagnostic findings;
- runbook used;
- actions attempted;
- outputs/results;
- technical verification;
- employee negative verdict;
- structured escalation assessment.

The value is that automated Tier-1 work is preserved rather than discarded.

## 7. Scenario C documentation

For a prohibited request, documentation should show:

```text
request refused before remediation
policy/security reason
no remediation execution
refusal recorded in audit
Human-L2 escalation/review
```

Do not generate a “successful remediation” report for a policy refusal.

## 8. Service Desk presentation

The current Service Desk exposes both forms of documentation without conflating them:

- Operational runbook: pre-existing knowledge used by the incident.
- Incident report: human-readable case-specific record.

The runbook may be rendered in a technician-friendly summary rather than showing raw YAML as the primary view, but its provenance should remain clear.

## 9. Future runbook creation

A production system could learn from recurring incidents, but automatically promoting model-generated commands into executable knowledge would create a serious trust boundary.

The proposed future workflow is therefore:

```text
historical knowledge / tickets / scripts
→ offline extraction/drafting
→ automated safety/schema checks
→ HUMAN REVIEW
→ approved version-controlled runbook
→ retrieval benchmark/regression
→ executable store
```

This future process is documented in `docs/rag-ingestion-strategy.md`. It is **not** a feature the current graded runtime claims to perform autonomously.
