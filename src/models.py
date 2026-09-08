from pydantic import BaseModel, Field
from typing import Optional
from enum import Enum


class Severity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    OPEN = "open"
    DIAGNOSING = "diagnosing"
    AWAITING_APPROVAL = "awaiting_approval"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class SafetyTier(str, Enum):
    GREEN = "green"
    YELLOW = "yellow"
    RED = "red"


class IncidentCreate(BaseModel):
    user_prompt: str = Field(..., min_length=1, description="User-reported issue text. Must not be empty.")
    category: Optional[str] = None


class IncidentResponse(BaseModel):
    id: str
    created_at: str
    user_prompt: str
    category: Optional[str] = None
    severity: Optional[str] = None
    status: str
    hostname: Optional[str] = None
    os_version: Optional[str] = None
    resolution_summary: Optional[str] = None
    runbook_id: Optional[str] = None


class ApprovalRequest(BaseModel):
    incident_id: str
    command: str
    description: str
    safety_tier: str


class AuditEntry(BaseModel):
    id: Optional[int] = None
    incident_id: str
    timestamp: str
    agent_name: str
    action_type: str
    safety_tier: str
    command_executed: Optional[str] = None
    output: Optional[str] = None
    user_approved: int = 0


class AgentMessage(BaseModel):
    agent_name: str
    message: str
    action_type: str
    safety_tier: SafetyTier
    command: Optional[str] = None


# =========================================================
# Escalation Ticket schema
# Pre-packaged Tier 2/3 hand-off payload sent to ServiceNow /
# Jira. Matches the contract defined in docs/user-journey.md.
# =========================================================

class DeviceTelemetry(BaseModel):
    """Read-only telemetry collected from the endpoint."""
    hostname: str
    os_version: str
    uptime_hours: float = 0.0
    last_boot_reason: str = "unknown"


class Requester(BaseModel):
    """The end user who reported the incident."""
    username: str
    email: str = ""
    department: str = "unknown"


class AttemptedRemediation(BaseModel):
    """One remediation the agent already attempted and verified."""
    action: str
    result: str
    verification_outcome: str


class IssueContext(BaseModel):
    """What happened, what was tried, and the agent's assessment."""
    user_reported_symptom: str
    detected_error_codes: list[str] = []
    attempted_remediations: list[AttemptedRemediation] = []
    agent_assessment: str


class EscalationTicket(BaseModel):
    """Typed contract for a Tier 2/3 escalation ticket."""
    ticket_title: str
    priority: str = "P3 - Moderate"
    requester: Requester
    device_telemetry: DeviceTelemetry
    issue_context: IssueContext
    incident_id: str = ""
