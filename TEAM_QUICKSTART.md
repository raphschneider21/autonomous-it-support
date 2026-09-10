# Team Quickstart — Current Integrated Project

This guide is for teammates opening the repository after the three original workstreams have been integrated.

Repository:

```text
raphschneider21/autonomous-it-support
```

The current product baseline is documented in:

```text
docs/final-demo-plan.md
README.md
CLAUDE.md / GEMINI.md
```

Do **not** use the old initial workstream split in `docs/roadmap.md` as an instruction to restart those tasks. Historical workstream documents remain useful for understanding how the product was built.

## 1. Clone/update the repository

```bash
cd ~/Documents
git clone https://github.com/raphschneider21/autonomous-it-support.git
cd autonomous-it-support
```

If already cloned:

```bash
git switch main
git pull --ff-only
```

Before making a change, create a task-specific branch rather than working directly on `main` unless the team explicitly agrees otherwise.

Example:

```bash
git switch -c docs/my-documentation-task
```

## 2. Python environment

Use a virtual environment if one is not already prepared:

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
```

Run the full suite with:

```bash
python3 -m pytest -q
```

## 3. Understand the current demo before changing anything

The graded path runs on one Mac:

```text
Employee Support / Incident Engine       :8000
Demo Lab                                 :8000/static/demo.html
Simulated Ubuntu endpoint                ubuntu-demo-01
Service Desk / Live Operations           :8001
```

The endpoint is simulated. The graded profile is deterministic/mock-backed for reliability.

Read:

```text
docs/final-demo-plan.md
.agents/rules/safety.md
docs/schema.md
```

before changing runtime behaviour, interfaces or safety.

## 4. One-click demo launch

In Finder, the prepared launcher is:

```text
scripts/demo/Autonomous IT Support Demo.command
```

Stop only launcher-owned demo processes with:

```text
scripts/demo/Stop Autonomous IT Support Demo.command
```

Full launch/preflight/rehearsal instructions are in:

```text
scripts/demo/README.md
```

## 5. Canonical scenarios

The accepted demo baseline has three outcomes:

```text
A. CUPS/printing fault → technically fixed → employee confirms solved → closed
B. CUPS/printing fault → technically fixed → employee says Still Broken → Human L2
C. Prohibited admin/security request → refused before remediation → escalated
```

There is also a disagreement/reconciliation scenario:

```text
Our team cannot access the ERP; users report a strange prompt
```

Do not change these flows casually; they are shared integration contracts and presentation evidence.

## 6. How to use an AI coding assistant safely

When starting a task, tell the assistant to:

1. read `docs/final-demo-plan.md`;
2. read the current task-specific documentation;
3. inspect the current code before proposing changes;
4. work only on the agreed branch/scope;
5. run relevant tests;
6. explain what changed in plain language;
7. stop before merging to `main` unless explicitly authorised.

For a teammate who wants more operational guidance, a useful opening instruction is:

```text
Read the repository instructions and current demo plan first. I may be unfamiliar with terminal/Git commands, so give me exact copyable commands one step at a time, explain what each step is doing briefly, and do not make destructive Git changes or merge to main without asking me.
```

## 7. Current documentation truth rules

Do not write or present that:

- the deterministic graded demo is using live Claude inference;
- simulated remediation changed the Mac host;
- a pre-existing runbook was generated during the incident;
- the current flow has a per-command approval modal;
- ServiceNow/Jira is actually integrated;
- an old test count is still current without rerunning the suite.

The current consent model is one up-front troubleshooting consent plus a strict default-deny runtime policy.

## 8. Current documentation/evidence map

```text
docs/final-demo-plan.md          accepted product/demo baseline
docs/problem-scope.md            business case and scope
docs/user-journey.md             employee/L1/L2 lifecycle
docs/schema.md                   current API/data contracts
docs/tdd.md                      working final TDD source
docs/tdd-evidence.md             engineering evidence dossier
docs/benchmark-round2.md         deterministic before/after benchmark
data/benchmarks/round1-live.json live Claude evaluation evidence
.agents/rules/live-demo-spec.md  15-minute presentation plan
.agents/rules/safety.md           current safety/consent policy
```

## 9. Before pushing a change

At minimum:

```bash
git status
python3 -m pytest -q
git diff --check
```

Then commit only the intended files and push the task branch.

If a test fails, do not delete/weaken it merely to obtain green status. Understand whether the implementation or the test is stale first.
