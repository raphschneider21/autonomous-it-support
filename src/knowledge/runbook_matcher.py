import json
import re
from typing import Optional
from .runbook_parser import load_all_runbooks


def match_runbook(user_prompt: str, error_codes: list[str] = None) -> Optional[dict]:
    runbooks = load_all_runbooks()
    best_match = None
    best_score = 0

    prompt_lower = user_prompt.lower()

    for rb in runbooks:
        score = 0
        triggers = rb.get("trigger_signatures", {})

        # Match symptoms
        symptoms = triggers.get("symptoms", [])
        for symptom in symptoms:
            symptom_lower = symptom.lower()
            words = symptom_lower.split()
            matches = sum(1 for w in words if w in prompt_lower)
            score += matches

        # Match error codes
        if error_codes:
            rb_codes = triggers.get("error_codes", [])
            for code in error_codes:
                if code in rb_codes:
                    score += 10

        # Match tags
        tags = rb.get("tags", [])
        for tag in tags:
            if tag.lower() in prompt_lower:
                score += 3

        if score > best_score:
            best_score = score
            best_match = rb

    if best_score >= 3:
        return best_match
    return None
