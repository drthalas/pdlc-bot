# pdlc-bot

Local Telegram-based PDLC orchestration bot for creating development task workspaces and Codex-ready prompts.

Version `0.1` creates local task artifacts and a Codex-ready prompt. It does not run the Codex CLI, create branches, commit code, push to Git, call GitHub, or create pull requests.

The bot currently runs in prompt/artifact mode. Codex Runner is disabled by default; the future runner is specified in [docs/CODEX_RUNNER_V0.md](docs/CODEX_RUNNER_V0.md). See [docs/ROADMAP.md](docs/ROADMAP.md) for the broader PDLC roadmap.

## Features

- Telegram commands: `/start`, `/projects`, `/status`, `/tasks`, `/task <TASK-ID>`, `/prompt <TASK-ID>`
- Telegram text messages become local development tasks
- Optional Telegram user allowlist
- YAML project registry with names and aliases
- Local `tasks/TASK-0001` style workspaces
- Generated artifacts:
  - `input.md`
  - `project.json`
  - `analysis.md`
  - `implementation_plan.md`
  - `codex_prompt.md`
- SQLite task index using the Python standard library

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Configure Environment

Create `.env` from the example:

```bash
cp .env.example .env
```

Set at least:

```bash
TELEGRAM_BOT_TOKEN=your-telegram-bot-token
```

Optionally restrict access to specific Telegram users:

```bash
TELEGRAM_ALLOWED_USER_IDS=123456789,987654321
```

If `TELEGRAM_ALLOWED_USER_IDS` is empty, any Telegram user who can reach the bot is allowed. Do not leave it empty when running the bot with a real Telegram token.

## Safe Live Run

Never publish `TELEGRAM_BOT_TOKEN` or paste it into logs, screenshots, chats, or GitHub. Set `TELEGRAM_ALLOWED_USER_IDS` before starting the bot with a real token.

If a Telegram token is accidentally exposed, rotate it through BotFather and update only the local `.env` on the machine that runs the bot.

The Telegram runtime configures noisy HTTP and Telegram library loggers at `WARNING` level so polling logs do not print sensitive Telegram API URLs.

## Configure Projects

Create `config/projects.yaml` from the example:

```bash
cp config/projects.example.yaml config/projects.yaml
```

`config/projects.yaml` is a local runtime config and is ignored by Git. Do not commit machine-specific project paths or private project metadata.

Example project entry:

```yaml
projects:
  - name: example-api
    aliases:
      - api
      - backend
    repo_url: https://github.com/example/example-api.git
    local_path: /path/to/example-api
    stack:
      - Python
      - FastAPI
      - SQLite
    context_files:
      - README.md
      - app/main.py
    test_commands:
      - pytest
    risk_level: medium
```

Project names and aliases are matched against incoming Telegram task text.

## Run Locally

Run the Telegram bot:

```bash
source .venv/bin/activate
python -m app.telegram_bot
```

Run the optional FastAPI status API:

```bash
source .venv/bin/activate
uvicorn app.main:app --reload
```

Useful endpoints:

- `GET /health`
- `GET /projects`
- `GET /tasks`

## Telegram UX

The bot uses a persistent bottom menu for navigation:

- `🏠 Menu`
- `📋 Projects`
- `🗂 Tasks`
- `ℹ️ Status`

The bottom menu is for navigation and remains available while using the bot. Inline buttons are still used for actions tied to a specific message or task.

- `/start` opens the main menu.
- `/projects` lists configured projects with project detail buttons.
- `/tasks` shows recent tasks with task detail buttons.
- New task responses include buttons for task details, Codex prompt, and recent tasks.

The slash commands `/start`, `/projects`, `/status`, `/tasks`, `/task TASK-ID`, and `/prompt TASK-ID` remain available for direct lookup.

Task messages include a `▶️ Run Codex` button, but Codex Runner is disabled by default. This version does not run Codex CLI.

Runner configuration uses:

```bash
PDLC_ENABLE_CODEX_RUNNER=false
PDLC_CODEX_RUNNER_MODE=disabled
PDLC_CODEX_BIN=/opt/homebrew/bin/codex
PDLC_CODEX_TIMEOUT_SECONDS=900
```

Supported runner modes:

- `disabled`: show a safe message and do nothing.
- `prepare`: create manual-run artifacts in the task workspace:
  - `run_codex_command.txt`
  - `run_codex.sh`
- `branch_prepare`: create manual branch-preparation artifacts in the task workspace:
  - `git_status_before.txt`
  - `branch_name.txt`
  - `run_codex_command.txt`
  - `run_codex.sh`
- `git_check`: run only a read-only `git status --porcelain` check in the target repo:
  - if the working tree is dirty, save `git_status_before.txt` and stop;
  - if the working tree is clean, also create `branch_name.txt`, `run_codex_command.txt`, and `run_codex.sh`.
- `branch_create`: run `git status --porcelain`, create a new branch with `git checkout -b <branch>`, then run `git status --porcelain` again:
  - if the working tree is dirty, save `git_status_before.txt` and stop;
  - if branch creation fails, save stdout/stderr/exit-code artifacts and stop;
  - if branch creation succeeds, also create `branch_name.txt`, `git_status_after_branch.txt`, `run_codex_command.txt`, and `run_codex.sh`.
- `codex_run`: after a clean git check and branch creation, run Codex CLI with `codex_prompt.md` as stdin:
  - saves Codex stdout/stderr/exit-code;
  - saves `git_status_after.txt`, `diff.patch`, `test_report.md`, and `developer_report.md`;
  - runs project test commands from `project.json`, falling back to `.venv/bin/pytest` and `.venv/bin/python -m app.main`;
  - does not commit, push, create PRs, or deploy.

Prepare modes still do not execute Codex CLI, commit, push, or deploy. They only write command text, scripts, and branch-preparation metadata for a human to inspect and run manually.

`branch_prepare` currently does not execute `git status` from the bot because subprocess execution is intentionally disabled at this stage. It writes a placeholder `git_status_before.txt` with a TODO for the future checked runner.

`git_check` uses a narrow read-only subprocess command with a timeout:

```bash
git status --porcelain
```

It still does not execute Codex CLI, create branches, checkout, commit, push, or deploy.

`branch_create` is the first mode that may change the target repo by creating a local branch. It allows only these subprocess commands, with `shell=False` and a timeout:

```bash
git status --porcelain
git checkout -b <branch>
git status --porcelain
```

It still does not execute Codex CLI, run `run_codex.sh`, commit, push, create PRs, or deploy.

`codex_run` is the first mode that may execute Codex CLI. It allows these subprocess command families, with `shell=False` and timeouts:

```bash
git status --porcelain
git checkout -b <branch>
<codex_bin> < codex_prompt.md
git diff
git diff --stat
<project test commands>
```

It still does not run `run_codex.sh`, commit, push, create PRs, or deploy.

## Mac mini operations

Persistent deployment uses a user-level `launchd` service on the Mac mini under user `hermes`. The bot currently runs in Telegram MVP mode: task creation, local artifacts, `/task`, and `/prompt`.

See [docs/MAC_MINI_RUNBOOK.md](docs/MAC_MINI_RUNBOOK.md) for service status, logs, restart, update, and security procedures.

## Roadmap

- [PDLC roadmap](docs/ROADMAP.md)
- [Codex Runner v0.1 specification](docs/CODEX_RUNNER_V0.md)

## Project memory files

Short memory files keep future Codex sessions focused:

- [PROJECT_CONTEXT.md](PROJECT_CONTEXT.md)
- [TASKS.md](TASKS.md)
- [DECISIONS.md](DECISIONS.md)

## Development Flow

1. Send a task message to the Telegram bot.
2. The bot detects the project by name or alias.
3. The bot creates a task folder like `tasks/TASK-0001`.
4. Use `/task TASK-0001` to review the task status, workspace, and generated artifacts.
5. Use `/prompt TASK-0001` to show the generated Codex prompt in Telegram.
6. Review `codex_prompt.md` in the workspace if the prompt is too long for Telegram.
7. Use the prompt manually with Codex when ready.

This first version intentionally avoids automatic code editing, Codex CLI execution, Git branch/commit/push workflows, pull request creation, and other remote service calls.
