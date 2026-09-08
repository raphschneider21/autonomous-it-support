# 🚀 Team Quickstart: Repository & AI Agent Setup

Welcome to the **Autonomous Enterprise IT Support Agent** project! 

This guide gets you set up in **under 5 minutes**—from cloning the repository to having your Antigravity AI agent fully synced with the project context, living documentation, and rules.

---

## 1. Accept Your GitHub Invite (1 Minute)
1. Check your email (or go to [github.com/notifications](https://github.com/notifications)).
2. Look for the invite to **`raphschneider21/autonomous-it-support`**.
3. Click **"Accept Invitation"**.

---

## 2. Clone the Repository (1 Minute)
Open your terminal and clone the repository into your preferred folder (e.g., your `Documents` or `Projects` folder):

```bash
cd ~/Documents
git clone https://github.com/raphschneider21/autonomous-it-support.git
cd autonomous-it-support
```

---

## 3. Connect Antigravity to the Project (1 Minute)
To ensure your AI agent automatically loads all project rules, architecture bounds, and safety guidelines:

1. Open **Antigravity** (or Antigravity IDE).
2. Click **File > Open Folder...** (or switch workspace).
3. Select your cloned **`autonomous-it-support`** directory.
4. **How to verify it's connected**:
   - Antigravity automatically detects `GEMINI.md` and `.agents/rules/`.
   - Start a fresh chat and send this prompt:
     > *"Read `GEMINI.md` and confirm you understand the project scope and our 4 living documents."*
   - The agent should confirm it sees `problem-scope.md`, `documentation-model.md`, `user-journey.md`, and `roadmap.md`.

---

## 4. Our 3-Way Workload Division (Claim Your Role)
We have broken down the initial modeling phase into 3 distinct subsystems in `docs/roadmap.md` so we can work in parallel without stepping on each other:

| Role | Subsystem Focus | Your Primary Document to Review/Refine |
| :--- | :--- | :--- |
| **`@Dev1`** | **Diagnostic Engine & Safety** | [`docs/problem-scope.md`](docs/problem-scope.md) (Define Green/Yellow/Red command boundaries) |
| **`@Dev2`** | **Memory & Dual Documentation** | [`docs/documentation-model.md`](docs/documentation-model.md) (AI Runbook YAML + Human Incident Report) |
| **`@Dev3`** | **Client UX & Escalation** | [`docs/user-journey.md`](docs/user-journey.md) (Consent UI flow + ServiceNow/Jira ticket JSON) |

Reply in the Teams chat with which role you want to take!

---

## 5. Day-to-Day Workflow & Best Practices

### A. The Branching Rule (Never code directly on `main`)
Always create a feature branch for your work:
```bash
git checkout -b feature/devX-initial-review
```
When finished, push your branch and open a Pull Request (PR) on GitHub for peer review:
```bash
git add .
git commit -m "docs: refine problem scope and edge cases"
git push -u origin feature/devX-initial-review
```

### B. Prompting Your Agent for Your Task
When working on your assigned items, prompt your agent like this:
> *"I am Dev [1/2/3]. Read `GEMINI.md` and `docs/roadmap.md`. Let's work on my assigned items in [your assigned document]. Proposed changes should adhere to `.agents/rules/`."*

### C. Free Token Hygiene (Keep it Fast & Free!)
- **One Task per Chat**: Start a fresh conversation for every new task. Because our project memory lives in `docs/` and `GEMINI.md`, you don't need a single endless chat that burns token quotas.
- **Inspect Specific Files**: Don't dump huge command outputs into the chat—let the agent inspect specific files directly.
