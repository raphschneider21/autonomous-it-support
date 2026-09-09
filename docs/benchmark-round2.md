# Benchmark Comparison: Round 1 (Before) vs Round 2 (After)

> Evidence artifact for **TDD Section 5: Performance Optimization** and
> **rubric #4 / #6**. Raw data in `data/benchmarks/round1.json` and
> `data/benchmarks/round2.json`, regenerated with
> `python -m tests.test_suite_runner --round <N>`.

## Summary

| Metric            | Round 1 (Before) | Round 2 (After) | Delta                          |
| ----------------- | ---------------- | --------------- | ------------------------------ |
| Accuracy          | 100%             | 100%            | no change                      |
| Avg latency (ms)  | 6.5              | 3.3             | **-49%** (2x faster)           |
| Avg tool calls    | 2.22             | 2.22            | no change (correctness intact) |
| Max latency (ms)  | 9.1              | 9.7*            | see note below                 |

\* TC-001 is the first runbook-match incident in a fresh process, so it pays
the one-time YAML load cost (cache cold miss). All subsequent incidents reuse
the cache.

## Change made

`src/knowledge/runbook_parser.py` — `load_all_runbooks()` now caches the parsed
runbook list at module level and only re-reads YAML when a runbook file changes
(validated via mtime). Previously every incident re-opened + re-parsed every
YAML file from disk during matching.

This is the dominant per-incident cost for runbook-match cases. The cache is
invalidated correctly (unit-tested) so fixture edits during development are
still picked up.

Secondary change: `src/engine/diagnostic_agent.py` deduplicates identical
diagnostic commands, guaranteeing no duplicate probes in one pass.

## Per-case comparison (latency, ms)

| Case | Expected        | Before | After |
| ---- | --------------- | ------ | ----- |
| TC-001 | runbook_match | 9.1    | 9.7 (cold cache) |
| TC-002 | runbook_match | 8.1    | 3.3   |
| TC-003 | runbook_match | 9.0    | 3.5   |
| TC-004 | escalate       | 7.3    | 2.9   |
| TC-005 | escalate       | 7.7    | 2.9   |
| TC-006 | blocked        | 0.8    | 1.0   |
| TC-007 | blocked        | 0.8    | 0.9   |
| TC-008 | diagnose       | 8.1    | 2.8   |
| TC-009 | diagnose       | 7.4    | 2.8   |
| TC-010 | error          | 0.0    | 0.0   |

## Interpretation

- Runbook-match incidents that were previously 8-9 ms now resolve in ~3 ms once
  the runbook store is warm — a realistic production profile (the same ~dozen
  runbooks serve all recurring incidents).
- Tool-call count is unchanged at 2.22, confirming the optimization reduced
  compute (I/O + parsing) without changing *agent reasoning*, keeping
  correctness and audit evidence identical.
- Accuracy remains 100% across all 10 cases.