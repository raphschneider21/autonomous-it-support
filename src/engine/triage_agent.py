import json
from datetime import datetime
from ..models import AgentMessage, SafetyTier
from ..safety.safety_validator import validate_command, is_allowed


TRIAGE_PROMPT = """You are a Triage Agent for an enterprise IT support system.
Classify the user's issue into ONE category and severity level.

Categories: network, printer, office, legacy, frozen
Severity: low, medium, high, critical

Respond with ONLY a JSON object:
{"category": "...", "severity": "...", "symptoms": ["..."], "reasoning": "..."}"""


def classify_incident(user_prompt: str, mock_response: str = None) -> dict:
    if mock_response:
        try:
            return json.loads(mock_response)
        except json.JSONDecodeError:
            pass

    return {
        "category": "unknown",
        "severity": "medium",
        "symptoms": [user_prompt],
        "reasoning": "Unable to classify automatically. Manual review recommended.",
    }


def classify_from_mock(user_prompt: str) -> dict:
    prompt_lower = user_prompt.lower()

    if any(w in prompt_lower for w in ["printer", "print", "spooler", "queue", "document"]):
        return {
            "category": "printer",
            "severity": "medium",
            "symptoms": ["Print job stuck", "Printer not responding"],
            "reasoning": "User mentions printer-related keywords. Classified as printer issue.",
        }
    if any(w in prompt_lower for w in ["vpn", "network", "internet", "dns", "connect"]):
        return {
            "category": "network",
            "severity": "high",
            "symptoms": ["Network connectivity issue", "VPN failure"],
            "reasoning": "User mentions network/VPN keywords. Classified as network issue.",
        }
    if any(w in prompt_lower for w in ["teams", "outlook", "office", "email", "crash"]):
        return {
            "category": "office",
            "severity": "medium",
            "symptoms": ["Application crash", "Office suite failure"],
            "reasoning": "User mentions Office/collaboration app keywords.",
        }
    if any(w in prompt_lower for w in ["slow", "frozen", "hang", "stuck", "cpu", "memory"]):
        return {
            "category": "frozen",
            "severity": "high",
            "symptoms": ["Unresponsive process", "High resource usage"],
            "reasoning": "User mentions performance/freeze keywords.",
        }

    return {
        "category": "unknown",
        "severity": "medium",
        "symptoms": [user_prompt],
        "reasoning": "Could not auto-classify. Defaulting to medium severity.",
    }
