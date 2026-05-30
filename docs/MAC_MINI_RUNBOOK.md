# Mac mini Runbook

Operational notes for the `pdlc-bot` Telegram MVP running on the Mac mini.

## Mac mini deployment overview

- Project path: `/Users/hermes/projects/pdlc-bot`
- Local environment file: `/Users/hermes/projects/pdlc-bot/.env`
- Local project registry: `/Users/hermes/projects/pdlc-bot/config/projects.yaml`
- Task artifacts: `/Users/hermes/projects/pdlc-bot/tasks`
- LaunchAgent plist: `/Users/hermes/Library/LaunchAgents/com.drthalas.pdlc-bot.plist`
- stdout log: `/Users/hermes/Library/Logs/pdlc-bot/stdout.log`
- stderr log: `/Users/hermes/Library/Logs/pdlc-bot/stderr.log`

## Current launchd service

- Label: `com.drthalas.pdlc-bot`
- Program: `/Users/hermes/projects/pdlc-bot/.venv/bin/python -m app.telegram_bot`
- Working directory: `/Users/hermes/projects/pdlc-bot`
- Mode: user-level LaunchAgent for user `hermes`

## Check service status

```bash
ssh hermes-mini 'launchctl print gui/$(id -u)/com.drthalas.pdlc-bot 2>/dev/null || true'
ssh hermes-mini 'pgrep -af "app.telegram_bot" || true'
```

## Check logs

```bash
ssh hermes-mini 'tail -n 100 /Users/hermes/Library/Logs/pdlc-bot/stdout.log 2>/dev/null || true'
ssh hermes-mini 'tail -n 100 /Users/hermes/Library/Logs/pdlc-bot/stderr.log 2>/dev/null || true'
```

Never print or publish `TELEGRAM_BOT_TOKEN`. If a token appears in logs, screenshots, chat, or GitHub, rotate it through BotFather and update only the local `.env` on the Mac mini.

## Stop service

```bash
ssh hermes-mini 'launchctl bootout gui/$(id -u) /Users/hermes/Library/LaunchAgents/com.drthalas.pdlc-bot.plist'
```

Fallback:

```bash
ssh hermes-mini 'launchctl unload /Users/hermes/Library/LaunchAgents/com.drthalas.pdlc-bot.plist'
```

## Start/reload service

```bash
ssh hermes-mini 'launchctl bootstrap gui/$(id -u) /Users/hermes/Library/LaunchAgents/com.drthalas.pdlc-bot.plist'
ssh hermes-mini 'launchctl kickstart -k gui/$(id -u)/com.drthalas.pdlc-bot'
```

Fallback:

```bash
ssh hermes-mini 'launchctl load /Users/hermes/Library/LaunchAgents/com.drthalas.pdlc-bot.plist'
```

## Restart service

```bash
ssh hermes-mini 'launchctl bootout gui/$(id -u) /Users/hermes/Library/LaunchAgents/com.drthalas.pdlc-bot.plist 2>/dev/null || true'
ssh hermes-mini 'launchctl bootstrap gui/$(id -u) /Users/hermes/Library/LaunchAgents/com.drthalas.pdlc-bot.plist'
ssh hermes-mini 'launchctl kickstart -k gui/$(id -u)/com.drthalas.pdlc-bot'
```

## Update deployment from GitHub

Safe update flow:

1. On the MacBook: develop, run tests, commit, and push.
2. On the Mac mini: stop the service.
3. Check the working tree.
4. If clean, pull from GitHub.
5. Install dependencies if needed.
6. Run tests and the import/startup check.
7. Start the service.
8. Run a Telegram smoke test.

Commands:

```bash
ssh hermes-mini 'cd /Users/hermes/projects/pdlc-bot && git status'
ssh hermes-mini 'cd /Users/hermes/projects/pdlc-bot && git pull'
ssh hermes-mini 'cd /Users/hermes/projects/pdlc-bot && .venv/bin/pip install -r requirements.txt'
ssh hermes-mini 'cd /Users/hermes/projects/pdlc-bot && .venv/bin/pytest'
ssh hermes-mini 'cd /Users/hermes/projects/pdlc-bot && .venv/bin/python -m app.main'
```

Do not pull over local source changes. `config/projects.yaml`, `.env`, `tasks/`, and SQLite files are local runtime files and should stay uncommitted.

## Telegram smoke test

After restart or update, check:

- `/start`
- `/projects`
- `/status`
- Create a test task
- `/task TASK-XXXX`
- `/prompt TASK-XXXX`

## Security checklist

- Do not commit `.env`.
- Keep `config/projects.yaml` local unless a sanitized example is intentionally committed.
- Keep `tasks/` ignored.
- Keep SQLite files ignored.
- `TELEGRAM_ALLOWED_USER_IDS` must be non-empty before polling.
- The Telegram token is only for `@drthalas_pdlc_bot`.
- Codex CLI is not launched automatically yet.
- GitHub automation is not enabled yet.
- Before any Developer Agent stage, create a separate SSH key for the Mac mini.

## Future roadmap

Future full cycle:

```text
Intake → Analyst → Architect → Developer → Tester/QA → Reviewer → Fix loop → PR/Deploy
```

Tester/QA Agent is required in the roadmap:

- Tester runs automated checks.
- Tester analyzes test failures.
- Tester creates a test report.
- If failures are found, the task returns to the Developer Agent fix loop.
- A separate Telegram interface or separate QA bot can be added later for QA/Test workflows.
