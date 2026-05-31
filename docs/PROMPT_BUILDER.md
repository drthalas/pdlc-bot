# Prompt Builder

`pdlc-bot` turns short Telegram task requests into structured Codex prompts. The goal is to give Codex enough project context, task-specific detail, safety constraints, and verification guidance without requiring the user to paste a large manual prompt.

Prompts should be mostly Russian when the user's request is Russian. Technical artifact filenames, internal status values, file paths, callback identifiers, and code identifiers may remain English.

## Codex Prompt Structure

Every generated `codex_prompt.md` should follow this structure:

1. `Ты Codex, работаешь над TASK-XXXX`
2. `Target project`
   - project name
   - `repo_url`
   - `local_path`
3. `User request`
   - the original user request without changing its meaning
4. `Project memory / context`
   - `PROJECT_CONTEXT.md`
   - `TASKS.md`
   - `DECISIONS.md`
   - `README.md`
   - `docs/ROADMAP.md`
   - `docs/CODEX_RUNNER_V0.md`
   - relevant `docs/*.md`
   - `docs/MAC_MINI_RUNBOOK.md` when the task mentions Mac mini, deployment, launchd, service operations, or runbooks
5. `Permanent project rules`
   - all Telegram user-facing text should be Russian by default
   - technical artifact filenames, internal statuses, and code identifiers may remain English
   - Codex Runner must not commit, push, or deploy without explicit approval
   - Mac mini is the execution runtime
   - Railway dashboard / PDLC Control Center is planned later
   - Tester/QA Agent is mandatory in the future roadmap
   - keep scope minimal and do not touch unrelated files
6. `Task brief`
   - a short task-specific summary
7. `Current behavior`
   - what is currently wrong, weak, or inconvenient
8. `Desired behavior`
   - what should be true after the change
9. `Suggested files to inspect`
   - concrete files selected for the task topic
10. `Implementation plan`
   - 5-10 concrete steps for this task
11. `Acceptance criteria`
   - specific, testable checks
12. `Safety constraints`
   - what must not be done
13. `Out of scope`
   - what should explicitly not be implemented now
14. `Verification`
   - concrete commands to run
15. `Report format`
   - what Codex should report back

## Topic-Specific File Selection

For Telegram UX tasks, include files such as:

- `app/telegram_bot.py`
- `app/telegram_ui.py`
- `app/task_messages.py`
- `app/task_store.py`
- `app/post_run_controls.py`
- `tests/test_telegram_ui.py`
- `tests/test_task_messages.py`

For Codex Runner tasks, include files such as:

- `app/codex_runner.py`
- `app/post_run_controls.py`
- `docs/CODEX_RUNNER_V0.md`
- `tests/test_codex_runner.py`
- `tests/test_post_run_controls.py`

For Mac mini, deployment, launchd, service, or runbook tasks, include files such as:

- `docs/MAC_MINI_RUNBOOK.md`
- `README.md`
- `docs/ROADMAP.md`

When the task type is unclear, start with:

- `README.md`
- `PROJECT_CONTEXT.md`
- `TASKS.md`
- `DECISIONS.md`

## Acceptance Criteria Guidance

Telegram UX prompts should ask Codex to verify that:

- user-facing Telegram text is Russian
- required buttons are shown
- `callback_data` stays within Telegram's 64-byte limit
- old slash commands still work
- tests are added or updated

Codex Runner prompts should ask Codex to verify that:

- Codex is not run without explicit user action
- commit, push, PR, and deploy are not performed
- artifacts are saved
- subprocess behavior is tested through mocks
- safety checks are preserved

## Safety

Prompt Builder must keep generated prompts explicit about boundaries. Unless a user separately approves it, Codex must not run Telegram polling, run real Codex CLI, execute `run_codex.sh`, commit, push, deploy, alter `.env`, expose tokens, or modify unrelated files.
