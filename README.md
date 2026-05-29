# pdlc-bot

Local Telegram-based PDLC orchestration bot for creating development task workspaces and Codex-ready prompts.

Version `0.1` only creates local artifacts and Telegram responses. It does not edit code, run shell commands, run Git, call GitHub, or call the Codex CLI.

## Features

- Telegram commands: `/start`, `/projects`, `/status`
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
python3.11 -m venv .venv
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

If `TELEGRAM_ALLOWED_USER_IDS` is empty, any Telegram user who can reach the bot is allowed.

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
python -m app.telegram_bot
```

Run the optional FastAPI status API:

```bash
uvicorn app.main:app --reload
```

Useful endpoints:

- `GET /health`
- `GET /projects`
- `GET /tasks`

## Development Flow

1. Send a task message to the Telegram bot.
2. The bot detects the project by name or alias.
3. The bot creates a task folder like `tasks/TASK-0001`.
4. Review `codex_prompt.md`.
5. Use the prompt manually with Codex when ready.

This first version intentionally avoids automatic code editing or remote service calls.
