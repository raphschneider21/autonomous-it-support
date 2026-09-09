"""Triage Agent — classifies a reported problem into a category and severity.

Claude does the classification. The keyword ladder below is kept as a declared
fallback for when no API key is configured or a call fails: it is a demoted
path, not the primary one, and `_source` on the returned dict records which ran
so the TDD can report how often each was used.

Categories are aligned with the Ubuntu 26.04 runbook store so triage and
retrieval agree on vocabulary.
"""
import json

from . import llm

CATEGORIES = llm.CATEGORIES

# Fallback keyword table. Ordered: the first category with a hit wins, so more
# specific vocabularies come before broader ones.
_KEYWORDS = [
    ("printing", ["print", "printer", "cups", "lpstat", "print queue", "spooler"]),
    ("audio", ["sound", "audio", "speaker", "microphone", "mic", "headphone",
               "volume", "muted", "pipewire", "pulseaudio"]),
    ("display", ["screen", "display", "monitor", "resolution", "brightness",
                 "external monitor", "hdmi", "flicker"]),
    ("packages", ["apt", "package", "install", "update", "upgrade", "dpkg",
                  "broken package", "software centre", "software center"]),
    ("time", ["clock", "time", "timezone", "date is wrong", "ntp", "behind"]),
    ("input", ["keyboard", "touchpad", "trackpad", "mouse", "layout", "typing"]),
    ("desktop", ["gnome", "desktop", "frozen", "hangs", "unresponsive",
                 "shell", "session", "log in", "login screen"]),
    ("disk", ["disk", "space", "full", "storage", "no space", "usb", "drive",
              "mount", "filesystem", "read-only"]),
    ("network", ["wifi", "wi-fi", "wireless", "internet", "network", "dns",
                 "resolve", "connection", "offline", "bluetooth", "ethernet"]),
]

_HIGH_SEVERITY = {"network", "disk"}


def classify(user_prompt: str) -> dict:
    """Classify an incident. Claude first, keyword ladder as declared fallback."""
    if user_prompt and user_prompt.strip():
        result = llm.call_agent(
            "TriageAgent",
            f"User-reported problem:\n{llm.wrap_evidence('user-report', user_prompt)}",
            expect_keys=("category", "severity"),
        )
        if result and result.get("category") in CATEGORIES:
            result.setdefault("symptoms", [user_prompt])
            result.setdefault("reasoning", "")
            return result

    fallback = classify_from_mock(user_prompt)
    fallback["_source"] = "keyword-fallback"
    return fallback


def classify_from_mock(user_prompt: str) -> dict:
    """Deterministic keyword classifier — the fallback path.

    Named `_from_mock` historically, when it was the only path. Kept under that
    name because the demo dry-run and the offline test suite call it directly.
    """
    if not user_prompt or not user_prompt.strip():
        return {
            "category": "unknown",
            "severity": "medium",
            "symptoms": [],
            "reasoning": "Empty report. Nothing to classify; escalating for human triage.",
        }

    lowered = user_prompt.lower()
    for category, words in _KEYWORDS:
        if any(word in lowered for word in words):
            return {
                "category": category,
                "severity": "high" if category in _HIGH_SEVERITY else "medium",
                "symptoms": [user_prompt.strip()],
                "reasoning": f"Report mentions {category} vocabulary.",
            }

    return {
        "category": "unknown",
        "severity": "medium",
        "symptoms": [user_prompt.strip()],
        "reasoning": "No category vocabulary matched. Escalating rather than guessing.",
    }
