# Problem Scope & Operational Boundaries

## 1. The Core Objective
Build an autonomous endpoint AI agent that acts as a reliable first responder for enterprise IT support. The agent resides on employee workstations, diagnoses common Tier-1 incidents, safely executes remediations, documents resolutions for both AI and human operators, and cleanly escalates unresolvable issues to human IT staff.

---

## 2. Tier 1 vs. Tier 2 Boundary Definition

| Metric | Tier 1 (Agent Autonomous Scope) | Tier 2 / 3 (Human Escalation Scope) |
| :--- | :--- | :--- |
| **Problem Type** | Repetitive, deterministic, endpoint-local, software cache/state issues. | Physical hardware faults, architecture changes, network topology failures, security compromises. |
| **Resolution Method** | Service restarts, cache flushes, adapter resets, registry tweaks, legacy script execution. | Hardware replacement, manual credential reassignment, deep forensic analysis, Active Directory re-provisioning. |
| **Risk / Blast Radius** | Local workstation only, reversible with clear rollback plans. | Organization-wide impact, data deletion risk, security perimeter alterations. |
| **Resolution Time** | 30 seconds to 3 minutes. | Hours to days. |

---

## 3. High-Frequency Target Issue Taxonomy

The agent will be designed to address the top 5 recurring enterprise workstation failure categories:

### Category A: Network & Connectivity Glitches
- **Symptoms**: "Internet connected but cannot reach internal intranet", "VPN connected with no traffic", "DNS resolution failed".
- **Agent Actions**: Flush DNS cache, release/renew DHCP lease, re-enable stuck virtual network adapters (e.g. Cisco AnyConnect, GlobalProtect), reset WinSock catalog.

### Category B: Peripheral & Print Subsystem Failures
- **Symptoms**: "Print job stuck in queue", "Printer offline error", "Cannot send print jobs".
- **Agent Actions**: Stop `spooler` service, clear stuck spool queue files in `System32\spool\PRINTERS`, restart `spooler` service.

### Category C: Collaboration & Office Application Lockups
- **Symptoms**: Teams/Outlook crashing on startup, corrupted authentication tokens, stuck sync loops.
- **Agent Actions**: Clear local application cache directories (e.g. `%appdata%\Microsoft\Teams`), remove stale Office identity tokens from Credential Manager, restart target process.

### Category D: In-House Legacy Scripts & Obscure Internal Apps
- **Symptoms**: 20-year-old internal billing/accounting tool fails with vague error (e.g., error 76: path not found).
- **Agent Actions**: Use RAG to locate internal documentation/known workarounds for that specific tool, verify mapped network drives (`net use`), set missing environment variables, run approved legacy remediation batch scripts.

### Category E: Frozen Processes & High Resource Utilization
- **Symptoms**: Machine sluggish, specific application unresponsive.
- **Agent Actions**: Identify high-CPU/hung process threads, prompt user for confirmation, cleanly terminate process (`Stop-Process`), prompt restart.

---

## 4. Hard Out-of-Scope Items (Never Attempted by Agent)
- Physical hardware troubleshooting (bad RAM, failing SSD, cracked display).
- Bypassing security policies, firewall rules, or Antivirus/EDR alerts.
- Creating or elevating Active Directory user permissions.
- Formatting drives, deleting system folders, or re-installing the OS.
