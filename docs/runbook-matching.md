# Runbook Matching — Algorithm Design & Measured Results

**Owner**: `@Dev2` (Knowledge Base & Documentation)
**Status**: Implemented — `src/knowledge/runbook_matcher.py`
**Corpus**: 30 runbooks, `fixtures/runbooks/ubuntu-26.04/` (Ubuntu 26.04 LTS VM)

---

## 1. What this component decides

Retrieval answers one question per incident: *have we solved this before, and
are we sure enough to act on it?* Its output drives the most consequential
branch in the whole engine — run a remediation on someone's machine, or hand
the incident to a human.

That framing sets three requirements:

| Requirement | Why |
| --- | --- |
| **Deterministic** | The same symptom must retrieve the same runbook every time, or the audit trail cannot be defended to a compliance reviewer. |
| **Explainable** | The report has to say *why* a runbook was chosen, not "the model picked it". |
| **Abstains under doubt** | Escalating a solvable incident costs a technician's time. Running the wrong remediation costs the user their machine state. These are not symmetric. |

**An LLM call was rejected for this step** (see `docs/architectural-decisions.md`,
Decision 17). Retrieval runs on every incident; an LLM would add network
latency and token cost to a lookup, introduce run-to-run variance into a
deterministic audit trail, and produce a confidence number that cannot be
justified. The LLM's value in this system is classification and summarisation,
not nearest-neighbour search over 30 documents.

---

## 2. The algorithm

### 2.1 Normalisation

Text on both sides (user prompt, runbook trigger signature) is lowercased and
tokenised, then:

- **Stopwords removed** — both standard English stopwords and a *domain*
  stopword list (`machine`, `laptop`, `computer`, `system`, `problem`,
  `working`, …). The domain list matters more than it looks: see §4.
- **Plural stemming** — a trailing `s` is stripped (`networks` → `network`)
  so a user's plural matches a runbook's singular.
- **Hyphen expansion** — `wi-fi` also yields `wifi`, and the tag
  `tap-to-click` also yields `tap` and `click`, so the tag matches a user who
  writes "tap to click".

### 2.2 Scoring

Each runbook is scored against the prompt over three fields, weighted by how
deliberately that field was written to be matched:

| Field | Weight | Rationale |
| --- | --- | --- |
| `trigger_signatures.symptoms` | 3.0 | Sentences authored specifically to describe how a user reports this issue. |
| `tags` | 2.0 | Curated keywords — high signal, no sentence context. |
| `title` | 1.5 | Incidental prose; helps, but was written for humans reading a report. |

Every matching token contributes `IDF(token) × field_weight`, where

```
IDF(t) = log(1 + N / (1 + df(t)))      N = corpus size, df = runbooks containing t
```

IDF is what separates the near-duplicate runbooks in this corpus. `RB-APT-001`,
`RB-APT-003` and `RB-APT-005` all repair a broken package state; the token
`apt` appears in all of them and is nearly worthless, while `interrupted`,
`unmet` and `upgrade` are decisive.

Two additional signals:

- **Phrase bonus** (`+2.5` per hit): contiguous bigrams shared between the
  prompt and a symptom sentence. Word-bag scoring cannot tell
  "the clock shows the wrong **time**" from "the clock shows the wrong
  **timezone**"; the bigram `(wrong, time)` can.
- **Error-code bonus** (`+6.0` per hit): a quoted error string
  (`Temporary failure in name resolution`, `E: Unable to locate package`) is
  near-conclusive evidence and outweighs prose similarity.

### 2.3 Confidence — and why the obvious formula was wrong

The first implementation normalised the score by the total IDF mass of the
prompt. It measured "how much of what the user said did we recognise", which
punishes a user for adding context words the corpus has never seen. On the
held-out set it rejected **8 correct matches** that were ranked first with a
healthy margin, purely because the sentence around them was verbose.

The shipped confidence is the geometric mean of two coverages:

```
prompt_coverage  = matched IDF mass / total prompt IDF mass
symptom_coverage = max over symptoms of (symptom tokens present in prompt / symptom tokens)
confidence       = sqrt(prompt_coverage × symptom_coverage)
```

Both halves are load-bearing. Prompt coverage alone penalises verbose users.
Symptom coverage alone rewards whichever runbook happens to have the shortest
trigger sentence. A genuinely out-of-scope prompt scores low on both.

`symptom_coverage` is also what resolves near-duplicates: a runbook that needs
a word the user never said (the "timezone" in "wrong timezone") is the weaker
candidate even when every word it *does* share is a hit.

### 2.4 The abstention rule

A runbook is returned only when **both** hold:

| Gate | Threshold | Rejects |
| --- | --- | --- |
| `confidence >= MIN_CONFIDENCE` | 0.35 | Prompts with no real overlap — hardware faults, gibberish, out-of-scope requests. |
| `margin >= MIN_MARGIN` | 0.08 | Prompts where the runner-up is too close to call. |

`margin = (best_score − runner_up_score) / best_score`.

Otherwise `match_runbook` returns `None` and the engine escalates with full
telemetry. `explain_match()` exposes the reason (`below_confidence_floor`,
`ambiguous_runner_up`) plus the top-3 candidates, so an escalation ticket can
state what the agent considered and why it declined.

Thresholds were selected by grid search over both evaluation sets
(§3), optimising for **zero wrong-runbook matches first**, accuracy second.

---

## 3. Measured results

Reproduce with `pytest tests/test_runbook_retrieval_benchmark.py`; the recorded
artifact is `data/benchmarks/retrieval-round1.json`.

### 3.1 Evaluation sets

| Set | Size | What it measures |
| --- | --- | --- |
| `tests/dataset_ubuntu_easy.json` | 33 | The team's training prompts, **verbatim**. |
| `tests/dataset_ubuntu_paraphrases.json` | 36 | Held-out paraphrases + 3 out-of-scope prompts. |

The verbatim set is a **sanity check, not evidence**. Each case's dataset
prompt was curated into the runbook that should retrieve it, so scoring 100%
on it partly measures copying. The paraphrase set is deliberately written in
different words from the stored trigger signatures, and is the number worth
quoting.

### 3.2 Errors split by consequence

Raw accuracy hides the distinction that matters:

- **`wrong`** — retrieved the *wrong* runbook. **Unsafe**: the agent proposes
  the wrong remediation for the user's machine. Target: zero.
- **`missed`** — retrieved nothing when a runbook existed. **Safe**: the
  incident escalates to a human, which is the designed fallback.

### 3.3 Before / after

| Matcher | Set | Accuracy | Correct | Escalated correctly | Missed (safe) | **Wrong (unsafe)** | p95 latency |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Word-overlap (previous) | verbatim | 90.9% | 30 | 0 | 0 | **3** | 0.09 ms |
| Word-overlap (previous) | held-out | 69.4% | 25 | 0 | 0 | **11** | 0.10 ms |
| IDF + abstention (current) | verbatim | **100%** | 30 | 3 | 0 | **0** | 0.15 ms |
| IDF + abstention (current) | held-out | **100%** | 30 | 6 | 0 | **0** | 0.14 ms |

The accuracy gain is secondary. The important column is the last error column:
the previous matcher had **no abstention path at all** — it returned its best
guess for every input, including inputs with no valid answer:

| Prompt | Word-overlap matcher | Current matcher |
| --- | --- | --- |
| "my screen is physically cracked and the hinge is broken" | `RB-APT-005` (would run `sudo dpkg --configure -a`) | escalate (conf 0.22) |
| "random text with no meaning xyz123 qwerty" | `RB-GNOME-003` (would kill a process) | escalate (conf 0.00) |
| "give the account full sudo rights and disable the firewall" | `RB-AUDIO-004` (would unmute audio) | escalate (conf 0.16) |
| "will not boot, drops to a grub rescue prompt" | `RB-GNOME-003` | escalate (conf 0.18) |

### 3.4 Latency

p95 **0.15 ms** per incident over a 30-runbook corpus, on top of a cached,
pre-built index (built once per store, invalidated on file change). Retrieval
is roughly three orders of magnitude below the diagnostic commands it
precedes, so it is not a target for further optimisation.

---

## 4. What the failures taught us

Recorded for TDD Section 3/4 — each of these was a real measured failure, not
a hypothetical.

**1. Small corpora make IDF lie.** The clock complaint *"the clock on my
machine is running about twenty minutes behind"* retrieved the **disk-full**
runbook, whose symptom reads *"the machine is running out of disk space"*.
With only 30 documents, generic words like `machine` and `running` appear in
one or two runbooks, so IDF scores them as highly discriminative — exactly
backwards. Fixed with an explicit domain stopword list. This is a property of
corpus size, and it will need revisiting as the knowledge base grows.

**2. Confidence must not punish verbosity.** See §2.3 — the first
normalisation rejected 8 correct, well-ranked matches because the user's
sentence contained words the corpus had not seen.

**3. Two failures were knowledge gaps, not algorithm gaps.** *"bluetooth
refuses to switch on, the slider flips straight back to off"* and *"everything
is silent and moving the volume slider changes nothing"* ranked correctly but
below the confidence floor, because the runbooks' trigger signatures never
mentioned a *slider*. The fix belonged in the knowledge base — two extra
symptom phrasings in `bt-001.yaml` and `audio-004.yaml` — not in the scorer.
Distinguishing "the retriever is wrong" from "the knowledge base is thin" is
the core maintenance loop of this subsystem.

---

## 5. Honest limits

- **The paraphrase set was authored by the same developer who wrote the
  runbooks**, and was then used to tune thresholds and to drive the two
  symptom additions above. It is therefore a *development* set: 100% on it is
  an upper bound, not an unbiased estimate. **Open team task**: `@Dev1` and
  `@Dev3` to each write 10 incident prompts without reading
  `fixtures/runbooks/ubuntu-26.04/`, as a genuinely blind test set.
- **Lexical, not semantic.** A user who writes "sound" where every runbook
  says "audio" is only caught because `audio` and `sound` both appear in the
  trigger signatures. Coverage comes from curating symptom phrasings, which
  does not scale indefinitely — §6 of `docs/rag-ingestion-strategy.md` covers
  when an embedding index earns its complexity.
- **Thresholds are tuned to a 30-runbook corpus.** IDF values shift as the
  corpus grows; the benchmark must be re-run and the thresholds re-checked
  whenever the store grows substantially. The benchmark test asserts zero
  unsafe matches, so this regression is caught rather than silently absorbed.
