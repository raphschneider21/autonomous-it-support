# Dual-Documentation System Specification

## 1. Rationale & Core Design
A critical innovation of this project is the strict separation between **AI-Executable Runbooks** and **Human-Readable Incident Reports**:
- **Why AI needs its own format**: LLMs reasoning from scratch on every ticket is slow, nondeterministic, and burns token quotas. When an issue is solved once, it is compiled into a deterministic, machine-readable runbook (YAML/JSON). The next time symptoms match, the agent executes the runbook directly with zero hallucination.
- **Why Humans need their own format**: IT administrators and compliance auditors need a clear, jargon-free summary of what the agent did, why it did it, which safety checks passed, and the exact timestamped actions taken.

---

## 2. Specification A: AI-Executable Runbook (YAML)

### Schema Definition
> **v1.1** (frozen 2026-09-09, `docs/schema.md` §1). Three optional fields
> were added additively: `parameters`, `environment`, `source_case`.

```yaml
schema_version: "1.1"
runbook_id: string                   # Unique ID, e.g., "RB-CUPS-001"
title: string                        # Descriptive name
target_os: string                    # "windows_11" | "ubuntu_26_04"
environment: string                  # v1.1: "vm-safe" | "physical-only"
source_case: string                  # v1.1: training-dataset case ID, e.g. "UB-029"
tags: [string]                       # Keywords for fast indexing

parameters:                          # v1.1: resolved into commands at load time
  - name: string                     # placeholder written as {name} in a command
    description: string              # what a technician should put here
    default: string                  # value used when nothing overrides it

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

### Real-World Example: Ubuntu 26.04 Stuck Print Queue (`RB-CUPS-001`)

The same schema on the Ubuntu 26.04 LTS VM endpoint. Note what the platform
forces: the fix is CUPS rather than the Windows spooler, verification is
read-only (`systemctl is-active`, `lpstat`), and every state-altering step
lands on the Yellow tier so the approval gate fires.

```yaml
schema_version: "1.1"
runbook_id: "RB-CUPS-001"
title: "Print Queue Stuck and Nothing Prints (CUPS Backlogged)"
target_os: "ubuntu_26_04"
environment: "vm-safe"
source_case: "UB-029"
tags: ["printer", "printing", "queue", "cups", "stuck", "spooler", "jobs"]

trigger_signatures:
  symptoms:
    - "Print jobs are stuck in the queue and nothing prints"
    - "the printer queue will not clear"
    - "documents sit in the print queue and never come out"
  error_codes: []

pre_checks:
  - id: "check_cups_state"
    command: "systemctl is-active cups"
    expected_output_regex: "active|inactive|failed"

remediation_steps:
  - step: 1
    description: "Cancel every queued print job"
    command: "cancel -a"
    elevation_required: false
    timeout_seconds: 20
  - step: 2
    description: "Restart the CUPS printing service"
    command: "sudo systemctl restart cups"
    elevation_required: true
    timeout_seconds: 30

verification:
  - command: "systemctl is-active cups"
    expected_output_regex: "^active"
  - command: "lpstat -o"
    expected_output_regex: "^$"
```

**Ubuntu 26.04 authoring constraints** (enforced by
`tests/test_ubuntu_knowledge_base.py`):

| Constraint | Consequence for runbook authors |
| --- | --- |
| GNOME 50 is **Wayland-only** — no X11 session | `xrandr`, `setxkbmap`, `xkill`, `wmctrl` reach XWayland clients only. Use `gdctl`, `gsettings`, `pkill`. |
| Audio is **PipeWire + WirePlumber** | `pulseaudio -k` is meaningless. Use `wpctl` (`pactl` still works via `pipewire-pulse`). |
| Removable media mount under **`/run/media`** | Verification regexes must not expect `/media`. |
| `sudo` is **sudo-rs**, coreutils are **uutils** | Output formats are close but not identical to GNU; verification regexes stay loose. |
| Endpoint is a **VM** | No Wi-Fi radio, touchpad or backlight. Those runbooks are marked `environment: physical-only`. |

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
