# Dev1 — Human Handoff Brief

**Your branch:** `feature/demo-runtime-reliability`  
**Your detailed contract:** `docs/workstreams/dev1-demo-runtime.md`  
**Overall demo plan:** `docs/final-demo-plan.md`

## What you are responsible for

Your job is to make the final live demo **actually work every time**.

You own the runtime behaviour behind the presentation: the simulated Ubuntu endpoint, the three rehearsed demo scenarios, the Demo Lab backend API, Service Desk reporting during incidents, demo reset/preflight, and the tests that prove those flows are reliable.

The other two developers are building what the audience sees. You are building the machinery that makes those screens tell the truth.

## The most important thing to build

The hero scenario is an Ubuntu **CUPS/printing failure**.

The demo must be able to start from a healthy simulated endpoint, inject a CUPS failure, let the existing troubleshooting engine observe that failure, run the existing `RB-CUPS-001` remediation through `MockExecutor`, change the simulated state back to healthy, and then verify the repaired state.

This must be **stateful simulation**, not just unrelated canned strings.

The real Ubuntu VM must not be damaged or modified during the graded demo.

## The three outcomes your lane must make dependable

1. **It fixes something:** the CUPS scenario resolves end-to-end.
2. **It knows when to hand over:** after technical verification, the employee can say the issue is still broken and the complete incident escalates from automated L1 to human L2.
3. **It refuses something:** the prompt-injection/security scenario executes no remediation command and is reported to the Service Desk.

A short Diagnostic/Security/Commander disagreement path must also remain available for the multi-agent part of the presentation.

## What Dev3 needs from you

Dev3 is building the Employee Support and Demo Lab frontend. Give that frontend these stable endpoints:

```text
GET  /api/demo/state
POST /api/demo/faults/{fault_id}
POST /api/demo/reset
```

The exact response contract is already specified in `docs/workstreams/dev1-demo-runtime.md`. Do not change it casually.

Dev3 should not need to understand or modify the engine or executor to finish her work.

## What Dev2 needs from you

Dev2 is building the Service Desk and Live Operations experience.

The endpoint should report the incident to the Service Desk early enough that a ticket can appear and visibly progress while the troubleshooting run is happening, not only after everything is finished.

Keep the existing ticket payload backward-compatible. The detailed contract also defines optional `incident_report` and `runbook` fields that Dev2 may display.

## What you should not work on

Do not redesign the Employee Support UI or Service Desk UI. Those belong to Dev3 and Dev2.

Do not enable real operating-system execution or make the graded demo depend on a live LLM/API. The final demo path is intentionally mock-backed and deterministic.

Do not redesign `docs/final-demo-plan.md`. If you discover a genuine architectural problem, bring it back to the team rather than silently changing the product plan.

## How to work

Use your AI assistant heavily. Give it the Dev1 AI bootstrap prompt supplied by the project. Let it inspect the repository, plan the implementation, edit code, run tests, debug failures, and help you prepare the PR.

Work only on:

```text
feature/demo-runtime-reliability
```

Do not work directly on `main`.

## You are finished when

You can demonstrate all of the following from a clean reset:

- Demo Lab reports a healthy simulated Ubuntu endpoint.
- `cups_stopped` can be injected and observed by diagnostics.
- The CUPS runbook repairs the simulated state.
- Verification observes CUPS as healthy afterwards.
- Reset is safe and repeatable.
- A ticket appears/progresses on the Service Desk during the run.
- `Still Broken` produces an L2 escalation carrying previous work.
- The injection scenario is refused with zero remediation execution.
- The disagreement/reconciliation moment still works.
- Demo/preflight makes mock mode and monitoring connectivity obvious.
- Relevant automated tests pass and the existing suite is not broken.

When those are true, push your branch and open a PR back to `main` with the rehearsal/test evidence requested in your detailed contract.

**Do not optimise for adding more features. Optimise for a demo that is safe, deterministic, understandable, and boringly reliable.**
