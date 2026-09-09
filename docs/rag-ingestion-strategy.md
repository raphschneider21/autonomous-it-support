# RAG Ingestion Strategy — Legacy Enterprise Scripts into the Knowledge Base

**Owner**: `@Dev2` (Knowledge Base & Documentation)
**Status**: Design — informs Milestone 6; not implemented in the PoC
**Roadmap item**: Milestone 0, `@Dev2` — *"Draft strategy for ingesting internal
legacy enterprise scripts into a vector index (RAG)"*

---

## 1. The problem this solves

Every enterprise service desk sits on a decade of undocumented institutional
fixes: `.sh` and `.ps1` scripts on a share, wiki pages, closed ticket
resolutions, `#it-support` chat threads. That corpus is exactly the knowledge
a Tier-1 agent needs, and it is exactly the corpus that cannot be trusted
as-is.

The strategy below is therefore **not** "embed everything and retrieve at
runtime". It is a pipeline that converts unstructured institutional knowledge
into *reviewed, executable runbooks*, and uses retrieval only where retrieval
is safe.

---

## 2. The core constraint: retrieved text must never become an executed command

This is the design decision everything else follows from.

A naive RAG agent retrieves a legacy script and executes what it finds. In
this system that would be a **remote code execution path with a search engine
in front of it**: any attacker who can write to the wiki, close a ticket with
a crafted resolution note, or drop a file on the scripts share, chooses what
runs on an endpoint. `.agents/rules/safety.md` and the prompt-injection
defences in `src/engine/security_agent.py` exist precisely to prevent
untrusted text from steering execution, and an ingestion pipeline must not
open a side door around them.

**Rule**: retrieved content is *evidence for a human author*, never an
instruction to an executor. The only thing the engine ever executes is a
committed, reviewed runbook in `fixtures/runbooks/`, whose every command has
passed `validate_command`.

This splits the design into two loops with very different trust levels.

---

## 3. Loop A — Offline ingestion (build time, human-gated)

```
legacy scripts ──┐
wiki articles ───┼──> 1. harvest ──> 2. normalise ──> 3. cluster ──> 4. draft
closed tickets ──┘                                                      │
                                                                        v
                                        6. commit to store <── 5. HUMAN REVIEW
```

**1. Harvest.** Pull `.sh`/`.ps1`/`.py` from the scripts share, wiki exports,
and resolved tickets from ServiceNow/Jira. Record provenance for every item
(source URI, author, last-modified, ticket ID) — provenance is what makes a
generated runbook auditable later.

**2. Normalise.** Strip credentials and hostnames, resolve `#`-comments into
intent statements, and reduce each artifact to a candidate triple:
`(symptom text, commands, verification)`. Ubuntu-specific: flag any command
using a subsystem 26.04 removed (`xrandr`, `setxkbmap`, `xkill`, `wmctrl`,
`pulseaudio -k`) — a large share of a legacy Linux script library will be
X11-era and cannot simply be carried across. The knowledge-base test suite
already asserts this invariant for shipped runbooks
(`tests/test_ubuntu_knowledge_base.py::test_no_command_uses_a_subsystem_removed_in_2604`).

**3. Cluster.** Embed the *symptom* text (not the commands) and cluster, so
the forty variations of "printer stuck" collapse into one candidate runbook
with forty observed phrasings. This is the highest-value use of embeddings in
the whole pipeline, and it is entirely offline.

**4. Draft.** An LLM converts each cluster into a `schema_version: "1.1"`
RunbookSchema draft: symptoms from the observed phrasings, commands from the
script, verification from whatever the script checked at the end. Output is a
YAML *proposal*, and the LLM sees the script as data, never as instructions.

**5. Human review — the mandatory gate.** A drafted runbook is inert until a
technician approves it. The reviewer confirms the commands do what the
description claims, that tiers are right, and that verification actually
proves the fix. Automated pre-review checks run first and block on failure:

- every command is non-Red (`validate_command`)
- every state-altering step is Yellow, i.e. approval-gated
- pre-checks and verification are read-only
- no removed-subsystem commands
- verification passes against the mock endpoint

These are the same invariants already enforced in
`tests/test_ubuntu_knowledge_base.py`, so ingestion inherits the existing
safety bar for free rather than inventing a second one.

**6. Commit.** The approved runbook lands in `fixtures/runbooks/<store>/` with
its provenance recorded, and the retrieval benchmark re-runs to confirm the
new entry did not degrade retrieval for existing incidents (§6).

---

## 4. Loop B — Runtime retrieval (per incident)

At runtime the agent touches **two** stores, with different privileges:

| Store | Content | Privilege |
| --- | --- | --- |
| Runbook store (`fixtures/runbooks/`) | Reviewed, executable YAML | May be **executed**, subject to the approval gate |
| Reference index (wiki, tickets, script docs) | Untrusted institutional text | May be **quoted** into a report or an escalation ticket. Never executed. |

The reference index earns its place on the **escalation** path, not the
remediation path. When retrieval abstains (`docs/runbook-matching.md` §2.4),
the escalation ticket today carries telemetry and the agent's assessment. With
a reference index it can also carry *"3 similar closed tickets: INC-4471,
INC-5012, INC-5588"* — which is what actually shortens a Tier-2 technician's
work, and it does so without any command ever being executed from retrieved
text.

---

## 5. Why the current PoC does not use a vector index

Deliberate, and worth stating plainly for the TDD:

- The corpus is **30 runbooks**. Exact IDF-weighted lexical matching gets
  100% on the held-out set at 0.15 ms p95 (`docs/runbook-matching.md` §3).
  An embedding index cannot beat 100%, and would add a model dependency, an
  index build step, and non-determinism to an audit-critical decision.
- Embeddings would make the *decision* harder to defend. "Cosine similarity
  0.83" is not an explanation a compliance reviewer can act on; "matched
  symptom tokens `[dpkg, interrupted, configure]`, confidence 0.71, runner-up
  0.31" is.
- Nothing is wasted by waiting: the ingestion pipeline above uses embeddings
  where they are genuinely better (offline clustering of symptom phrasings),
  which is a different job from runtime retrieval.

---

## 6. When to revisit

Concrete triggers, so this is a decision with an expiry date rather than a
permanent preference:

| Trigger | Action |
| --- | --- |
| Corpus > ~200 runbooks | Re-run the benchmark. IDF behaviour changes with corpus size (`docs/runbook-matching.md` §4) and the thresholds will need re-tuning. |
| Held-out accuracy drops below ~90% | Add a hybrid stage: lexical retrieval for the top-20, embedding re-rank within it. Keep the abstention gates on the final score. |
| Curated symptom phrasings exceed ~8 per runbook | The lexical matcher is being hand-fed synonyms; that is the point where embeddings start paying for themselves. |
| Multi-language incident reports | Lexical matching does not survive translation. Embeddings become necessary, not optional. |

Any of these is a schema-affecting change and requires a new entry in
`docs/architectural-decisions.md`.

---

## 7. Open questions for the team

- **`[TEAM INPUT]`** Which legacy source does FHNW's scenario assume — a
  scripts share, a wiki, or a ticket export? The harvest step differs per source.
- **`[TEAM INPUT]`** Who plays the reviewer role in step 5 for the demo? The
  human-review gate is the ethical centre of this design (rubric #10) and
  should be shown, not just described.
