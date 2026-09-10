# RAG Ingestion Strategy — Legacy Enterprise Knowledge into Reviewed Runbooks

**Status:** design/future work; not implemented in the current graded PoC.

This document describes how a future enterprise deployment could turn unstructured institutional knowledge into reviewed operational runbooks without creating a new execution bypass.

## 1. Problem

Service desks often accumulate useful but inconsistent knowledge in scripts, wiki pages, resolved tickets and team notes. That material can help build a Tier-1 knowledge base, but it cannot safely be treated as executable instruction merely because retrieval found it.

The design therefore separates:

```text
untrusted institutional knowledge
→ offline extraction/drafting
→ validation + human review
→ approved version-controlled runbook
→ runtime retrieval
```

from:

```text
runtime execution
→ current employee consent + strict allowlist + executor boundary
```

The human review gate in this document applies to **promoting knowledge into the executable runbook store**. It is not the same thing as a per-command approval modal during an incident.

## 2. Core trust rule

Retrieved text must never become executable merely because an LLM or search system returned it.

A naive RAG design that retrieves a script and executes it would let anyone who can influence the source corpus influence endpoint execution. Examples include a malicious wiki edit, a crafted closed-ticket note, or a poisoned shared script.

Therefore:

> Retrieved content is evidence for offline authoring or Human-L2 context. The runtime executes only reviewed runbook commands that still pass the current safety validator.

A committed runbook is still not trusted unconditionally. Runtime parameters/placeholders must be resolved and the final command must pass the default-deny validator before the executor receives it.

## 3. Loop A — offline ingestion and authoring

```text
scripts ─────┐
wiki pages ──┼──> harvest → normalise → cluster → draft → validate → HUMAN REVIEW → commit
closed tickets┘
```

### 3.1 Harvest

Collect candidate knowledge with provenance:

- source system/location;
- source identifier;
- author/owner when available;
- last-modified timestamp;
- ticket/script/document relationship.

Production ingestion would also need access controls and data-retention/minimisation decisions before sensitive ticket content is processed.

### 3.2 Normalise

Reduce source material to candidate facts such as:

```text
symptoms
observed errors/evidence
candidate diagnostic commands
candidate remediation commands
verification checks
```

Strip secrets, credentials and environment-specific identifiers where appropriate.

The source text remains untrusted data. Instruction-shaped text from a source must not be treated as an instruction to the drafting model or runtime.

### 3.3 Cluster/retrieve related knowledge

Embeddings can be useful **offline** for grouping similar symptom descriptions across many historic sources. This is a different use case from directly retrieving a command at runtime.

Only symptom/context representations should influence clustering. Executable content remains subject to later review and validation.

### 3.4 Draft

A model may convert a cluster into a candidate RunbookSchema document, but the result is inert.

The draft can propose:

- symptoms/signatures;
- pre-checks;
- remediation steps;
- verification;
- rollback guidance;
- provenance metadata.

It is not placed directly into the executable store.

### 3.5 Automated pre-review checks

Candidate runbooks should be rejected before human review if they violate mechanical invariants, for example:

- schema invalid;
- missing remediation/verification where required;
- pre-check/verification is state-altering;
- final command fails the safety validator;
- unresolved parameter placeholder;
- forbidden/Red command;
- command targets a subsystem unsupported by the target endpoint profile;
- duplicate/conflicting runbook identifier.

For the current codebase, the same validation principles already used by the Ubuntu runbook tests should be reused rather than creating a separate safety definition.

### 3.6 Human review — knowledge promotion gate

A qualified reviewer decides whether the candidate should become executable operational knowledge.

The reviewer should verify:

- the command does what the description claims;
- the remedy is appropriate for the intended blast radius;
- the runtime safety tier/allowlist relationship is correct;
- verification genuinely detects recovery rather than only command success;
- rollback/exception handling is reasonable;
- provenance is sufficient;
- the runbook does not expose secrets or unsafe environment-specific assumptions.

Only after review is the runbook committed/versioned in the approved store.

### 3.7 Commit and regression

After promotion:

- add the runbook to the version-controlled store;
- run schema/safety tests;
- rerun retrieval benchmarks;
- check that new symptom signatures do not cause unacceptable false matches;
- record the provenance/reviewer/version.

## 4. Loop B — runtime retrieval

At runtime there are two conceptually different knowledge classes:

| Knowledge class | Trust | Runtime use |
| --- | --- | --- |
| Reviewed operational runbook | Versioned and pre-reviewed, but still subject to runtime policy | May provide diagnostic/remediation/verification commands after final command validation |
| Untrusted reference corpus | Wiki/tickets/scripts/chat/etc. | May support human context/reporting or model reasoning as fenced evidence; never directly executable |

The current PoC uses the first class: a local reviewed YAML runbook store.

A future reference index would be most useful on ambiguous/escalation cases, for example:

```text
Three similar historical tickets were found
→ attach references/summaries to Human L2
→ do not execute their text
```

## 5. Relationship to current runtime consent

The current graded runtime uses one up-front troubleshooting consent.

```text
Green   read-only diagnostics                     automatic
Yellow  local/reversible + strict allowlist       allowed inside up-front consent
Red     forbidden                                 blocked
Unknown not explicitly allowlisted                blocked
```

A reviewed runbook does not override these rules.

This is separate from the **offline human review** described above. Offline review decides whether a runbook can enter the trusted operational knowledge store; runtime consent/policy decides whether a specific final command can execute in a specific incident.

## 6. Why the current PoC does not require a vector database

The current PoC has a small curated runbook corpus and an explainable lexical/IDF-style retrieval design with abstention thresholds. For this scale, adding an embedding service/vector database would create additional dependencies without necessarily improving the demonstrated result.

The current design also makes retrieval easier to explain and test: the project can record matched symptoms/tokens, score/margin and abstention rather than relying only on an opaque vector distance.

Embeddings become more attractive when the knowledge problem changes—for example:

- hundreds/thousands of runbooks;
- multi-language symptom descriptions;
- highly paraphrased/unstructured knowledge;
- offline clustering of historic ticket text;
- hybrid lexical + semantic retrieval.

## 7. Revisit triggers

Reasonable future triggers include:

| Trigger | Potential response |
| --- | --- |
| Runbook corpus grows substantially | Rebenchmark retrieval and consider hybrid lexical + embedding rerank |
| Held-out retrieval quality drops materially | Evaluate embeddings/reranking while retaining abstention |
| Symptom synonym lists become manually excessive | Use semantic retrieval to reduce hand-authored phrasing |
| Multi-language support becomes a requirement | Evaluate multilingual embeddings/models |
| Historic-ticket reference search becomes important | Build a non-executable reference index for Human-L2 context |

Any new runtime retrieval approach should preserve provenance, abstention, command validation and auditability.

## 8. Current PoC truth statement

The graded system does **not** claim to ingest enterprise scripts or generate new executable runbooks autonomously.

What it demonstrates today is:

```text
pre-existing reviewed runbook
→ match known symptoms
→ apply current runtime safety policy
→ simulate permitted remediation
→ verify fresh endpoint state
→ record which runbook was used
```

The ingestion strategy in this document is future architecture and should be labelled that way in the TDD/demo.

## 9. Team inputs for a future implementation

If this design is ever implemented, the team would need to decide with the target organisation:

- which source systems can be ingested;
- who is allowed to approve/promote runbooks;
- required provenance/audit retention;
- treatment of personal/sensitive ticket data;
- version/revocation process for unsafe or obsolete runbooks;
- retrieval quality thresholds and acceptance test set.
