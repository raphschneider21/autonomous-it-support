# Dual-Documentation System Specification

## 1. Rationale & Core Design
A critical innovation of this project is the strict separation between **AI-Executable Runbooks** and **Human-Readable Incident Reports**:
- **Why AI needs its own format**: LLMs reasoning from scratch on every ticket is slow, nondeterministic, and burns token quotas. When an issue is solved once, it is compiled into a deterministic, machine-readable runbook (YAML/JSON). The next time symptoms match, the agent executes the runbook directly with zero hallucination.
- **Why Humans need their own format**: IT administrators and compliance auditors need a clear, jargon-free summary of what the agent did, why it did it, which safety checks passed, and the exact timestamped actions taken.

---

## 2. Specification A: AI-Executable Runbook (YAML)

### Schema Definition
```yaml
schema_version: "1.0"
runbook_id: string                   # Unique ID, e.g., "RB-PRINT-001"
title: string                        # Descriptive name
target_os: string                    # "windows_11" | "windows_10" | "linux_ubuntu"
tags: [string]                       # Keywords for fast indexing

trigger_signatures:
  error_codes: [string]              # Event Viewer or API error codes
  process_names: [string]            # Related executables
  symptoms: [string]                 # Natural language symptom matches

pre_checks:                          # Read-only verification before action
  - id: string
    command: string                  # Diagnostic command
    expected_output_regex: string    # Must match to proceed

remediation_steps:                   # Ordered recovery actions
  - step: integer
    description: string
    command: string                  # Command to execute
    elevation_required: boolean      # Needs admin rights?
    timeout_seconds: integer

verification:                        # Confirms the fix worked
  - command: string
    expected_output_regex: string

rollback_plan:                       # Executed if remediation fails
  - command: string
```

### Real-World Example: Stuck Print Spooler (`RB-PRINT-001.yaml`)
```yaml
schema_version: "1.0"
runbook_id: "RB-PRINT-001"
title: "Clear Stuck Windows Print Spooler Queue"
target_os: "windows_11"
tags: ["printer", "spooler", "print-job-stuck", "offline"]

trigger_signatures:
  error_codes: ["EVENT_ID_372", "0x8007007b"]
  process_names: ["spoolsv.exe"]
  symptoms: ["Printer shows error", "Print jobs stuck in queue cannot delete"]

pre_checks:
  - id: "check_spooler_running"
    command: "Get-Service -Name spooler | Select-Object -ExpandProperty Status"
    expected_output_regex: "Running|Stopped"

remediation_steps:
  - step: 1
    description: "Stop the print spooler service"
    command: "Stop-Service -Name spooler -Force"
    elevation_required: true
    timeout_seconds: 15
  - step: 2
    description: "Delete stuck shadow files from spool folder"
    command: "Remove-Item -Path $env:SystemRoot\\System32\\spool\\PRINTERS\\* -Force -ErrorAction SilentlyContinue"
    elevation_required: true
    timeout_seconds: 10
  - step: 3
    description: "Restart the print spooler service"
    command: "Start-Service -Name spooler"
    elevation_required: true
    timeout_seconds: 15

verification:
  - command: "Get-Service -Name spooler | Select-Object -ExpandProperty Status"
    expected_output_regex: "Running"

rollback_plan:
  - command: "Start-Service -Name spooler"
```

---

## 3. Specification B: Human-Readable Incident Report (Markdown)

### Format Template
```markdown
# Incident Resolution Report: [INC-ID]
- **Timestamp**: YYYY-MM-DD HH:MM:SS
- **Host / User**: [Hostname] | [Username]
- **Target Application / Domain**: [App Name]
- **Initial User Prompt**: "[Quoted user problem description]"

### 1. Root Cause Summary
A concise, plain-English summary of what went wrong.

### 2. Actions Taken by Agent
Chronological audit log showing exact timestamps, actions, and safety tier:
- [HH:MM:SS] [Green] Diagnosed: ...
- [HH:MM:SS] [Yellow] User consented to: ...
- [HH:MM:SS] [Green] Verification: ...

### 3. Verification & Outcome
- **Verification Check**: [Pass / Fail details]
- **User Confirmation**: [Confirmed resolved / User declined / Auto-verified]
- **Runbook Linked/Created**: [Runbook ID or "None (New Case)"]
- **Final Status**: [RESOLVED | ESCALATED TO TIER 2]
```

### Real-World Example: Incident Report
```markdown
# Incident Resolution Report: INC-20260908-041
- **Timestamp**: 2026-09-08 10:15:22 UTC
- **Host / User**: WS-ENG-089 | user: jsmith
- **Target Application / Domain**: Windows Print Subsystem
- **Initial User Prompt**: "My document has been stuck printing for 20 minutes and I can't cancel it."

### 1. Root Cause Summary
The Windows Print Spooler (`spoolsv.exe`) had deadlocked on a corrupted `.SPL` file in the print queue directory, preventing any new jobs from reaching the physical printer.

### 2. Actions Taken by Agent
- [10:15:25] [Green] Query service status for `spooler`: Service was running but unresponsive to RPC calls.
- [10:15:28] [Yellow] Prompted user to restart print service and clear print buffer. User clicked **Approve**.
- [10:15:30] [Yellow] Force-stopped `spooler` service.
- [10:15:32] [Yellow] Removed 2 orphaned spool files from `C:\Windows\System32\spool\PRINTERS\`.
- [10:15:35] [Yellow] Restarted `spooler` service.
- [10:15:38] [Green] Verified service state: Returned `Running`.

### 3. Verification & Outcome
- **Verification Check**: Print queue query returned 0 stuck jobs. Service responding normally.
- **User Confirmation**: User tested printing a test page and clicked "Yes, It's Fixed".
- **Runbook Linked**: `RB-PRINT-001.yaml` (Executed successfully in 16 seconds).
- **Final Status**: RESOLVED (No human escalation required).
```
