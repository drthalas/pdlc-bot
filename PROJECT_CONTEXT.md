# Project Context

`pdlc-bot` is a local Telegram-based PDLC orchestration bot. It turns Telegram messages into structured development task workspaces and Codex-ready prompt artifacts.

## Current Architecture

- `app.telegram_bot` is the Telegram control plane.
- `app.orchestrator` coordinates project detection, task creation, analysis, planning, and prompt generation.
- `ProjectRegistry` loads configured projects and aliases from `config/projects.yaml`.
- `TaskStore` persists task metadata in SQLite.
- `TaskWorkspace` writes local task artifacts under `tasks/TASK-XXXX`.
- Prompt Builder expands short Telegram requests into structured Codex prompts with project memory, task-specific plans, acceptance criteria, safety constraints, and verification commands.
- Codex Runner is gated by feature flags and safe modes. It can prepare artifacts, check git state, create task branches, and run Codex CLI only through explicit user action. It still does not commit, push, create PRs, or deploy without approval.

## Runtime Split

- MacBook is the development machine.
- Mac mini is the runtime machine.
- Mac mini runs the Telegram bot continuously through user-level `launchd`.
- Telegram bot is the operational control plane for creating and inspecting PDLC tasks.

## Codex Runner

- Codex CLI is installed on Mac mini.
- Codex Runner is disabled by default.
- `prepare` and `branch_prepare` modes only write artifacts for manual inspection.
- `git_check` and `branch_create` add controlled git checks and branch creation.
- `codex_run` can execute Codex CLI after explicit user action and writes task artifacts.
- Runner modes do not commit, push, create PRs, or deploy without approval.

## Future Direction

- Railway dashboard/control center is planned later.
- Mac mini should remain the closed execution runtime.
- Railway should initially be read-only and receive events from Mac mini via outbound HTTPS.
- Tester/QA Agent is mandatory in the roadmap.
- Future PDLC loop: Intake -> Analyst -> Architect -> Developer/Codex -> Tester/QA -> Reviewer -> Fix loop -> PR/Deploy.
