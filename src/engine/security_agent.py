import re
from ..models import SafetyTier
from ..safety.safety_validator import validate_command


SECURITY_INDICATORS = [
    "unusual prompt",
    "strange prompt",
    "login prompt",
    "password prompt",
    "credential",
    "phishing",
    "verification code",
    "two-factor",
    "mfa",
    "authenticator",
    "strange window",
    "unknown dialog",
    "unexpected login",
    "suspicious",
    "unknown email",
    "unusual notification",
    "asked to enter password",
    "keeps asking",
    "fake",
    "harvest",
    "stolen",
    "compromised",
]


def assess_prompt(user_prompt: str) -> dict:
    """Inspect the user's prompt for signs of a security incident.

    Returns a structured assessment so the Incident Commander can reconcile
    the security reading against the Diagnostic Agent's infrastructure reading.
    """
    lowered = user_prompt.lower()
    hits = [w for w in SECURITY_INDICATORS if w in lowered]

    if hits:
        return {
            "agent": "SecurityAgent",
            "root_cause": "security/credential_harvesting",
            "evidence": f"Prompt contains security indicators: {', '.join(hits[:4])}.",
            "security_flagged": True,
        }

    return {
        "agent": "SecurityAgent",
        "root_cause": "infrastructure",
        "evidence": "No security indicators present in the user prompt.",
        "security_flagged": False,
    }


def check_action(command: str, context: str = "") -> dict:
    tier = validate_command(command)

    if tier == SafetyTier.RED:
        return {
            "allowed": False,
            "safety_tier": tier.value,
            "reason": "BLOCKED: This command is in the Red tier (forbidden). It poses security or system integrity risks.",
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


# Exact-phrase patterns (word-boundary aware) — these are HIGH confidence
# attempts to hijack the agent. Only match on deliberate instruction-override
# phrasing, not incidental mentions.
HIGH_CONFIDENCE_PATTERNS = [
    # Ignore previous / forget instructions
    r"\bignore\s+(?:all\s+)?(?:previous\s+|prior\s+|earlier\s+)?(?:instructions?|prompts?|messages?|rules?)\b",
    r"\bdisregard\s+(?:all\s+)?(?:previous\s+|prior\s+|earlier\s+)?(?:instructions?|prompts?|rules?)\b",
    r"\bforget\s+(?:all\s+)?(?:your\s+)?(?:previous\s+|prior\s+)?(?:instructions?|prompts?|rules?)\b",
    r"\boverwrite\s+(?:all\s+)?(?:instructions?|prompts?|rules?|prompt)\b",
    r"\boverride\s+(?:all\s+)?(?:instructions?|prompts?|rules?|safety|security)\b",
    r"\bnew\s+instructions?\b",
    r"\bnew\s+rules\b",
    # Repurposing the system
    r"\byou\s+are\s+now\s+",
    r"\bact\s+(?:as|like)\s+",
    r"\breveal\s+(?:your\s+|the\s+)?(?:prompt|system\s+prompt|instructions?)\b",
    r"\b[Ww]hat\s+is\s+(?:your\s+)?(?:system\s+)?prompt\b",
    # Bypass / elevation requests
    r"\bbypass\s+(?:the\s+)?(?:safety|security|approval|consent|authorization)\b",
    r"\bbypass\s+(?:all\s+)?restrictions\b",
    r"\bskip\s+(?:the\s+)?(?:safety|security|approval|consent)\b",
    r"\belevate\s+(?:my\s+)?(?:permissions?|privileges?|access|user)\b",
    r"\bgrant\s+(?:me\s+)?(?:root|admin|administrator|system)\b",
    r"\bgive\s+me\s+(?:root|admin|administrator|system)\s+access\b",
    r"\bunlock\s+(?:all\s+)?(?:permissions?|restrictions?|blocked\s+actions?)\b",
    r"\bdisable\s+(?:the\s+|your\s+|all\s+)?(?:safety|security|restrictions?|guardrails?)\b",
    # Turning off defenses
    r"\bdisable\s+(?:the\s+)?(?:firewall|antivirus|antivirus\s+software|edr|endpoint\s+protection|security\s+software)\b",
    r"\bturn\s+off\s+(?:the\s+)?(?:firewall|antivirus|edr|security\s+software)\b",
    # Acting with privilege we shouldn't
    r"\bdelete\s+system\b",
    r"\bwell\s+known\s+sid\b",
]

# Low-confidence / contextual patterns — flag higher only when they co-occur
# with other markers OR appear as a command, not when simply mentioned.
LOW_CONFIDENCE_TERMS = [
    r"\bignore\b",
    r"\bdisregard\b",
    r"\badmin\b",
    r"\badministrator\b",
    r"\broot\s+access\b",
    r"\bsudo\b",
    r"\belevat\w*\b",
    r"\bprivilege\w*\b",
    r"\bbypass\w*\b",
    r"\boverrid\w*\b",
    r"\bunlock\b",
]

_COMMANDS_PATTERN = re.compile(
    r"\b(net\s+user|net\s+localgroup|runas|privileged|netstat\s+-[^ ]*[o]|reg\s+add|dism|systemreset|info)\b",
    re.IGNORECASE,
)

_COMMAND_NAME = re.compile(
    r"^\s*(?:\w+:\\)?\s*([a-zA-Z0-9_\-]+(?:\.[a-zA-Z0-9]+)?)\b",
)

# Grouped for clarity
HIGH_COMPILED = [re.compile(p, re.IGNORECASE) for p in HIGH_CONFIDENCE_PATTERNS]
LOW_COMPILED = [re.compile(p, re.IGNORECASE) for p in LOW_CONFIDENCE_TERMS]


def detect_prompt_injection(user_input: str) -> bool:
    """Detect attempts to override, bypass, or elevate the agent's behavior.

    Returns True if the input likely contains a prompt-injection attempt.

    Strategy:
      1. High-signal phrases (ignore instructions, reveal prompt, disable
         firewall, escalate privileges) match and immediately flag.
      2. If none, score low-signal terms + command-shaped language; a
         combination of both is suspicious, a bare mention is not.
    """
    if not user_input or not user_input.strip():
        return False

    text = user_input.strip()

    # 1) High-confidence keyword/phrase detection
    for pattern in HIGH_COMPILED:
        if pattern.search(text):
            return True

    # 2) Command-style execution attempts (even obfuscated with whitespace)
    normalized = re.sub(r"\s+", " ", text).strip()
    cmd_match = _COMMANDS_PATTERN.search(normalized)
    if cmd_match:
        # A command that is red-tier or escalation-related is always flagged
        return True

    # 3) Score low-confidence terms. Require at least two distinct signals to
    #    reduce false positives on incidental mentions.
    hits = set()
    for pattern in LOW_COMPILED:
        if pattern.search(text):
            hits.add(pattern.pattern)

    # A bare admin mention is normally a benign support request.
    # Two or more low-signal terms together is suspicious.
    return len(hits) >= 2