# Codex Runner v0.1

Implementation status: started.

Current stage: disabled-by-default UI skeleton plus prepare-command-only mode. The Telegram button exists, the disabled response is safe, and prepare mode can write manual-run artifacts. No actual Codex execution happens yet.

## Goal

Today, the user copies `codex_prompt.md` into Codex manually and then brings the result back into the workflow.

Codex Runner v0.1 should remove that manual copy/paste step. The runner will execute Codex from a task-specific Telegram action, capture logs and diffs, run verification, and report results back to Telegram.

## Preconditions

- Codex CLI must be installed on the Mac mini.
- Codex CLI must be authorized through a ChatGPT subscription, not API billing.
- Current verified version: `codex-cli 0.135.0`.
- Current verified path: `/opt/homebrew/bin/codex`.
- Runner must use a configurable Codex path, not a hardcode-only path.

## UX

After task creation, show:

- `▶️ Run Codex`
- `📄 Task details`
- `🧠 Codex prompt`
- `🗂 Recent tasks`

When the user clicks `Run Codex`:

1. For low/medium risk tasks, ask for confirmation:
   ```text
   Run Codex for TASK-XXXX?
   ```
2. For high/critical risk tasks, block or require separate approval.
3. After confirmation:
   - status changes to `coding`;
   - a branch is created;
   - Codex CLI runs;
   - logs are saved;
   - diff is collected;
   - tests are run;
   - a report is created.

## Safety rules

- Codex Runner is disabled by default.
- It must be enabled through a config setting:
  ```text
  PDLC_ENABLE_CODEX_RUNNER=false
  ```
- Without enabling it, the runner button can respond:
  ```text
  Codex Runner is disabled.
  ```
- Prepare mode is non-executing:
  ```text
  PDLC_CODEX_RUNNER_MODE=prepare
  ```
  It writes `run_codex_command.txt` and `run_codex.sh` into the task workspace for manual inspection and manual execution later.
- Never run Codex automatically when a task is created.
- Run only after an explicit user click.
- Do not commit.
- Do not push.
- Do not create PRs.
- Do not deploy.
- Do not modify `.env`.
- Do not modify secrets.
- If the working tree is dirty, stop.
- If the task is high risk, stop and ask for approval.
- VPN, infra, and firewall tasks should be read-only or require extra approval.

## Suggested task statuses

Future statuses:

- `waiting_codex_approval`
- `coding`
- `code_done`
- `testing`
- `test_failed`
- `ready_for_review`
- `ready_to_commit`

These are not implemented yet.

## Artifacts

Codex Runner should save:

- `codex_prompt.md`
- `run_codex_command.txt`
- `run_codex.sh`
- `codex_stdout.log`
- `codex_stderr.log`
- `codex_exit_code.txt`
- `git_status_before.txt`
- `git_status_after.txt`
- `diff.patch`
- `test_report.md`
- `developer_report.md`

## Branch naming

Format:

```text
agent/TASK-XXXX-short-slug
```

Example:

```text
agent/TASK-0007-add-persistent-menu
```

## Verification

After Codex Runner finishes:

- `git status`
- `git diff --stat`
- project test commands from `projects.yaml`

Fallback verification:

- `.venv/bin/pytest`
- `.venv/bin/python -m app.main`

## Telegram report

After execution, send a summary:

- task id;
- branch;
- changed files;
- tests result;
- diff summary;
- artifacts created.

Next buttons:

- `🔍 Show diff`
- `🧪 Run tests again`
- `🔁 Ask Codex to fix`
- `✅ Mark ready for review`
- `❌ Stop`

## Implementation plan

1. Config flag + disabled button. Done.
2. Runner skeleton without Codex execution: prepare command only. Started with `run_codex_command.txt` and `run_codex.sh`.
3. Branch creation + git status checks.
4. Actual Codex CLI execution.
5. Logs/artifacts capture.
6. Test runner.
7. Telegram report.
8. Fix loop.
