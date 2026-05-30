# pdlc-bot

Local Telegram-based PDLC orchestration bot for creating development task workspaces and Codex-ready prompts.

Version `0.1` creates local task artifacts and a Codex-ready prompt. It does not run the Codex CLI, create branches, commit code, push to Git, call GitHub, or create pull requests.

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

The bot uses inline buttons for common actions:

- `/start` opens the main menu.
- `/projects` lists configured projects with project detail buttons.
- `/tasks` shows recent tasks with task detail buttons.
- New task responses include buttons for task details, Codex prompt, and recent tasks.

The text commands `/task TASK-ID` and `/prompt TASK-ID` remain available for direct lookup.

## Mac mini operations

Persistent deployment uses a user-level `launchd` service on the Mac mini under user `hermes`. The bot currently runs in Telegram MVP mode: task creation, local artifacts, `/task`, and `/prompt`.

See [docs/MAC_MINI_RUNBOOK.md](docs/MAC_MINI_RUNBOOK.md) for service status, logs, restart, update, and security procedures.

## Development Flow

1. Send a task message to the Telegram bot.
2. The bot detects the project by name or alias.
3. The bot creates a task folder like `tasks/TASK-0001`.
4. Use `/task TASK-0001` to review the task status, workspace, and generated artifacts.
5. Use `/prompt TASK-0001` to show the generated Codex prompt in Telegram.
6. Review `codex_prompt.md` in the workspace if the prompt is too long for Telegram.
7. Use the prompt manually with Codex when ready.

This first version intentionally avoids automatic code editing, Codex CLI execution, Git branch/commit/push workflows, pull request creation, and other remote service calls.
