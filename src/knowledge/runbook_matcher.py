"""Symptom -> runbook retrieval.

Matching is deliberately *not* an LLM call. Retrieval runs on every incident,
so it has to be deterministic, explainable in an audit trail, and fast enough
to be invisible next to the diagnostic commands. The algorithm is IDF-weighted
field matching over the runbook trigger signatures, with an explicit
confidence floor and a runner-up margin so an ambiguous incident escalates to a
human instead of being "fixed" with the wrong runbook.

See `docs/runbook-matching.md` for the design rationale and the measured
accuracy/latency figures.
"""
import math
import re
from typing import Optional

from .runbook_parser import load_all_runbooks, active_store

# Field weights: a symptom sentence is written to be matched, a tag is a
# curated keyword, a title is incidental prose.
W_SYMPTOM = 3.0
W_TAG = 2.0
W_TITLE = 1.5
W_MAX = W_SYMPTOM

W_PHRASE = 2.5       # bonus per contiguous prompt bigram found in a symptom
W_ERROR_CODE = 6.0   # a quoted error string is near-conclusive evidence

# An incident is only auto-remediated when retrieval is both confident in
# absolute terms and clearly ahead of the runner-up.
MIN_CONFIDENCE = 0.35
MIN_MARGIN = 0.08

_STOPWORDS = {
    "a", "about", "after", "again", "all", "am", "an", "and", "any", "anymore", "are", "as",
    "at", "be", "been", "but", "by", "can", "cannot", "cant", "do", "does", "doing", "dont",
    "even", "every", "few", "for", "from", "get", "gets", "getting", "had", "has", "have",
    "he", "her", "here", "his", "how", "i", "if", "in", "into", "is", "it", "its", "just",
    "keep", "keeps", "me", "more", "much", "must", "my", "no", "not", "of", "on", "once",
    "only", "or", "other", "our", "out", "over", "own", "please", "run", "same", "she",
    "should", "since", "so", "some", "still", "such", "than", "that", "the", "their",
    "them", "then", "there", "these", "they", "this", "those", "to", "too", "try", "trying",
    "up", "use", "very", "was", "we", "were", "what", "when", "where", "which", "while",
    "who", "why", "will", "with", "would", "you", "your",
}

# Domain stopwords: words every IT ticket contains, which therefore separate
# nothing. They must be removed explicitly — over a corpus of only ~30
# runbooks, IDF sees a generic word like "machine" as *rare* and treats it as
# discriminative, which is how "the clock on my machine is running behind"
# scored against "the machine is running out of disk space".
_DOMAIN_STOPWORDS = {
    "anything", "computer", "device", "everything", "issue", "laptop", "machine",
    "nothing", "pc", "problem", "something", "system", "thing", "ubuntu", "user",
    "work", "working", "works", "workstation",
}
_STOPWORDS |= _DOMAIN_STOPWORDS

_TOKEN_RE = re.compile(r"[a-z0-9][a-z0-9_.+/-]*")


def _stem(token: str) -> str:
    """Strip a trailing plural 's' so 'networks' and 'network' collide."""
    if len(token) > 3 and token.endswith("s") and not token.endswith("ss"):
        return token[:-1]
    return token


def _tokens(text: str) -> list[str]:
    """Ordered, stemmed content tokens. Hyphenated terms also yield their parts
    and their concatenation, so 'wi-fi' matches the tag 'wifi' and the prompt
    'tap to click' matches the tag 'tap-to-click'."""
    out: list[str] = []
    for raw in _TOKEN_RE.findall(text.lower()):
        raw = raw.strip("./-+_")
        if not raw:
            continue
        variants = [raw]
        if "-" in raw:
            variants.append(raw.replace("-", ""))
            variants.extend(p for p in raw.split("-") if p)
        for v in variants:
            if len(v) < 2 or v in _STOPWORDS:
                continue
            stemmed = _stem(v)
            if stemmed not in _STOPWORDS:
                out.append(stemmed)
    return out


def _bigrams(tokens: list[str]) -> set[tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


def _index_runbook(rb: dict) -> dict:
    triggers = rb.get("trigger_signatures", {}) or {}
    symptoms = triggers.get("symptoms", []) or []

    symptom_tokens: set[str] = set()
    symptom_bigrams: set[tuple[str, str]] = set()
    symptom_sets: list[set[str]] = []
    for s in symptoms:
        toks = _tokens(s)
        symptom_tokens.update(toks)
        symptom_bigrams.update(_bigrams(toks))
        if toks:
            symptom_sets.append(set(toks))

    return {
        "runbook": rb,
        "symptoms": symptom_tokens,
        "symptom_sets": symptom_sets,
        "symptom_bigrams": symptom_bigrams,
        "tags": set(_tokens(" ".join(rb.get("tags", []) or []))),
        "title": set(_tokens(rb.get("title", "") or "")),
        "error_codes": [c.lower() for c in (triggers.get("error_codes", []) or [])],
    }


_index_cache: dict[str, tuple[int, list[dict], dict[str, float]]] = {}


def _build_index(store: str) -> tuple[list[dict], dict[str, float]]:
    """Index every runbook in a store and compute the IDF table.

    Cached per store and rebuilt whenever the parser hands back a different
    list object (i.e. whenever the runbook cache was invalidated).
    """
    runbooks = load_all_runbooks(store)
    cached = _index_cache.get(store)
    if cached and cached[0] == id(runbooks):
        return cached[1], cached[2]

    entries = [_index_runbook(rb) for rb in runbooks]
    n = len(entries)

    doc_freq: dict[str, int] = {}
    for e in entries:
        for token in e["symptoms"] | e["tags"] | e["title"]:
            doc_freq[token] = doc_freq.get(token, 0) + 1

    # Smoothed IDF. A token the corpus has never seen scores highest, which
    # inflates the confidence denominator — that is deliberate: an incident
    # full of unknown vocabulary should escalate, not match something.
    idf = {t: math.log(1 + n / (1 + df)) for t, df in doc_freq.items()}
    idf["__unseen__"] = math.log(1 + n)

    _index_cache[store] = (id(runbooks), entries, idf)
    return entries, idf


def _confidence(matched_mass: float, prompt_mass: float, symptom_cov: float) -> float:
    """Geometric mean of the two coverages — how much of what the user said was
    recognised, and how much of the runbook's trigger the user actually said.

    Both halves are needed. Prompt coverage alone punishes a user who adds
    context words the corpus has never seen; symptom coverage alone would
    reward a runbook with one short trigger sentence. A prompt about something
    genuinely out of scope scores low on both and escalates.
    """
    prompt_cov = matched_mass / prompt_mass if prompt_mass else 0.0
    return min(math.sqrt(max(prompt_cov, 0.0) * max(symptom_cov, 0.0)), 1.0)


def score_runbooks(user_prompt: str, error_codes: list[str] = None,
                   store: str = None) -> list[dict]:
    """Score every runbook in the store against a prompt, best first.

    Returned entries carry the raw score and the normalised confidence so the
    incident report and the audit trail can explain *why* a runbook was chosen.
    """
    store = store or active_store()
    entries, idf = _build_index(store)
    if not entries:
        return []

    prompt_tokens = _tokens(user_prompt)
    unique = list(dict.fromkeys(prompt_tokens))
    prompt_bigrams = _bigrams(prompt_tokens)
    prompt_lower = user_prompt.lower()
    supplied_codes = [c.lower() for c in (error_codes or [])]

    unseen = idf["__unseen__"]
    idf_mass = sum(idf.get(t, unseen) for t in unique) or 1.0

    prompt_set = set(unique)
    scored = []
    for e in entries:
        score = 0.0
        matched: list[str] = []
        matched_mass = 0.0

        for token in unique:
            weight = 0.0
            if token in e["symptoms"]:
                weight = W_SYMPTOM
            elif token in e["tags"]:
                weight = W_TAG
            elif token in e["title"]:
                weight = W_TITLE
            if weight:
                token_idf = idf.get(token, unseen)
                score += token_idf * weight
                matched_mass += token_idf
                matched.append(token)

        phrase_hits = len(prompt_bigrams & e["symptom_bigrams"])
        score += phrase_hits * W_PHRASE

        # How completely does the prompt cover this runbook's *own* trigger
        # sentence? A runbook that needs words the user never said (the
        # "timezone" in "wrong timezone") is the weaker candidate even when
        # every word it shares with the prompt is a hit. This feeds the
        # confidence score rather than the ranking score: measured over the
        # evaluation sets it separated ambiguous pairs without reordering
        # anything that was already ranked correctly.
        symptom_cov = max(
            (len(ss & prompt_set) / len(ss) for ss in e["symptom_sets"]), default=0.0
        )

        code_hits = 0
        for code in e["error_codes"]:
            if code and (code in prompt_lower or code in supplied_codes):
                code_hits += 1
        score += code_hits * W_ERROR_CODE

        scored.append({
            "runbook": e["runbook"],
            "runbook_id": e["runbook"].get("runbook_id"),
            "score": round(score, 3),
            "confidence": round(_confidence(matched_mass, idf_mass, symptom_cov), 3),
            "prompt_coverage": round(matched_mass / idf_mass, 3),
            "symptom_coverage": round(symptom_cov, 3),
            "matched_tokens": matched,
            "phrase_hits": phrase_hits,
            "error_code_hits": code_hits,
        })

    scored.sort(key=lambda s: s["score"], reverse=True)
    return scored


def match_runbook(user_prompt: str, error_codes: list[str] = None,
                  store: str = None) -> Optional[dict]:
    """Return the single best runbook, or None when the engine should escalate.

    None is returned when retrieval is not confident enough in absolute terms,
    or when the runner-up is too close to call. Both are escalation signals:
    executing the second-best runbook on someone's machine is worse than
    handing the incident to a human.
    """
    explained = explain_match(user_prompt, error_codes, store)
    return explained["runbook"] if explained["matched"] else None


def explain_match(user_prompt: str, error_codes: list[str] = None,
                  store: str = None) -> dict:
    """`match_runbook` with the decision trace attached, for audit and tests."""
    scored = score_runbooks(user_prompt, error_codes, store)
    if not scored:
        return {"matched": False, "runbook": None, "reason": "empty_runbook_store",
                "confidence": 0.0, "margin": 0.0, "candidates": []}

    best = scored[0]
    runner_up = scored[1] if len(scored) > 1 else None
    margin = 1.0 if not runner_up or best["score"] <= 0 else \
        round((best["score"] - runner_up["score"]) / best["score"], 3)

    if best["confidence"] < MIN_CONFIDENCE:
        reason = "below_confidence_floor"
    elif margin < MIN_MARGIN:
        reason = "ambiguous_runner_up"
    else:
        reason = "matched"

    return {
        "matched": reason == "matched",
        "runbook": best["runbook"] if reason == "matched" else None,
        "runbook_id": best["runbook_id"] if reason == "matched" else None,
        "reason": reason,
        "confidence": best["confidence"],
        "margin": margin,
        "candidates": [
            {k: v for k, v in c.items() if k != "runbook"} for c in scored[:3]
        ],
    }
