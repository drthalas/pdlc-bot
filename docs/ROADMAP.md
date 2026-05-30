# PDLC Bot Roadmap

## Current state

- Telegram MVP works.
- Mac mini deployment through user-level `launchd` works.
- Persistent Telegram lower menu works.
- Tasks are created from Telegram messages.
- Task artifacts are created:
  - `input.md`
  - `project.json`
  - `analysis.md`
  - `implementation_plan.md`
  - `codex_prompt.md`
- `/task`, `/prompt`, and `/tasks` work.
- Inline buttons work.
- Persistent lower menu works.
- Codex CLI is installed on the Mac mini and the smoke test passed.

## Next: Codex Runner v0.1

Goal: remove manual prompt copy/paste by allowing an explicit, user-approved Codex run from Telegram.

Scope:

- Add a `▶️ Run Codex` button.
- Run Codex only after explicit user approval.
- Run Codex in a separate branch.
- Do not commit.
- Do not push.
- Do not create PRs.
- Do not deploy.
- Save stdout/stderr.
- Save `git diff`.
- Run tests after Codex.
- Return a report in Telegram.

See [CODEX_RUNNER_V0.md](CODEX_RUNNER_V0.md) for the detailed specification.

## Future: Tester/QA Agent

Tester/QA Agent is required in the roadmap.

- Tester runs automated checks.
- Tester analyzes test failures.
- Tester creates `test_report.md`.
- If failures are found, the task returns to the Developer Agent fix loop.
- A separate Telegram interface or separate QA bot can be added later for QA/Test workflows.

Future full cycle:

```text
Intake → Analyst → Architect → Developer/Codex → Tester/QA → Reviewer → Fix loop → PR/Deploy
```

## Future: Reviewer Agent

- Analyzes diffs.
- Looks for risks.
- Creates `review_report.md`.
- Can return a task to the fix loop.
- Can mark a task as ready for commit.

## Future: GitHub PR mode

- Branch push.
- PR creation.
- PR summary.
- Telegram link to the PR.
- Explicit approval before push/PR.

## Future: Deploy mode

- Staging deploy.
- Smoke test.
- Production approval.
- Rollback plan.

## Future: Railway PDLC Control Center

Approved architecture:

- Railway will be used as a future external dashboard/frontend/control center.
- Mac mini remains the private execution runtime.
- Mac mini owns:
  - Telegram bot
  - Codex Runner
  - Tester/QA Agent
  - Reviewer Agent
  - local Git repositories
  - tasks/artifacts/logs
- Railway dashboard shows:
  - tasks
  - statuses
  - agent runs
  - event timeline
  - artifacts index
  - test reports
  - review reports
  - approvals
- First dashboard phase is read-only.
- Mac mini pushes events to Railway through outbound HTTPS.
- Railway must not directly call an internal Mac mini backend in early phases.
- Later, Railway can expose a command queue and Mac mini can pull commands itself.
- Dashboard is not implemented yet.
