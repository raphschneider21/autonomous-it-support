from ..models import SafetyTier
from ..safety.safety_validator import validate_command, is_allowed, RED_COMMANDS


def check_action(command: str, context: str = "") -> dict:
    tier = validate_command(command)

    if tier == SafetyTier.RED:
        return {
            "allowed": False,
            "safety_tier": tier.value,
            "reason": f"BLOCKED: This command is in the Red tier (forbidden). It poses security or system integrity risks.",
            "command": command,
        }

    if tier == SafetyTier.YELLOW:
        return {
            "allowed": True,
            "requires_approval": True,
            "safety_tier": tier.value,
            "reason": "This action modifies system state and requires explicit user approval.",
            "command": command,
        }

    return {
        "allowed": True,
        "requires_approval": False,
        "safety_tier": tier.value,
        "reason": "Read-only diagnostic command. Safe to execute.",
        "command": command,
    }


def detect_prompt_injection(user_input: str) -> bool:
    dangerous_patterns = [
        "ignore",
        "disregard",
        "forget your instructions",
        "forget all instructions",
        "you are now",
        "act as",
        "overwrite",
        "override",
        "bypass security",
        "bypass safety",
        "disable firewall",
        "disable antivirus",
        "disable edr",
        "elevate",
        "admin",
        "administrator",
        "root access",
        "sudo",
        "grant permissions",
        "grant access",
        "system prompt",
        "reveal prompt",
        "new instructions",
        "new rules",
        "unlock",
    ]
    input_lower = user_input.lower()
    return any(pattern in input_lower for pattern in dangerous_patterns)
