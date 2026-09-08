---
trigger: model_decision
description: Collaboration and Git conventions for the 3-developer team.
---

# Team Collaboration Conventions

Guidelines for `@Dev1`, `@Dev2`, and `@Dev3` to work seamlessly together without Git conflicts or prompt drift:

### 1. Branching & PRs
- Never push directly to `main`.
- Create short-lived feature branches: `feature/dev1-safety-gate`, `feature/dev2-runbook-schema`, `feature/dev3-client-ui`.
- Merge into `main` frequently via Pull Requests with peer review.

### 2. Updating Living Docs
- If you change a data structure or workflow, update the corresponding document in `docs/` in the exact same Git commit.
- Mark your assigned tasks as complete `[x]` in `docs/roadmap.md` on your branch before opening a PR.

### 3. Context & Token Hygiene (Free Tier Optimization)
- Keep AI prompts focused on a single file or task.
- Avoid pasting massive command logs into chats—pipe output or extract only the relevant stack trace.
- When starting a new task, open a fresh chat conversation and reference `GEMINI.md` to keep latency low and conserve free tokens.
