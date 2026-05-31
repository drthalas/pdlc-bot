# Codex Runner v0.1

Implementation status: started.

Current stage: disabled-by-default UI skeleton plus safe runner modes. The Telegram button exists, the disabled response is safe, `prepare` can write manual-run artifacts, `branch_prepare` can write branch-preparation artifacts, `git_check` can run a read-only `git status --porcelain` check before preparing artifacts, `branch_create` can create a local branch after a clean git check, and `codex_run` can execute Codex CLI after branch creation. Post-run controls can show the saved diff, request a confirmed local commit, request a separate confirmed branch push, or request a confirmed discard. No PR or deploy happens.

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
- `🗂 Последние`
- `🛠 Детали`

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
- Branch prepare mode is also non-executing:
  ```text
  PDLC_CODEX_RUNNER_MODE=branch_prepare
  ```
  It writes `git_status_before.txt`, `branch_name.txt`, `run_codex_command.txt`, and `run_codex.sh`. It does not create a branch, run `git checkout`, run Codex CLI, commit, push, or deploy.
- In the current no-subprocess stage, `branch_prepare` does not execute `git status` yet. `git_status_before.txt` records that this check is intentionally deferred until the checked runner stage.
- Git check mode performs only one read-only subprocess command:
  ```text
  PDLC_CODEX_RUNNER_MODE=git_check
  git status --porcelain
  ```
  The command runs in the target project repo with a timeout. If output is non-empty, the runner saves `git_status_before.txt` and stops. If output is empty, it writes `branch_name.txt`, `run_codex_command.txt`, and `run_codex.sh`. It still does not create branches, run `git checkout`, run Codex CLI, commit, push, or deploy.
- Branch create mode performs only these subprocess commands:
  ```text
  PDLC_CODEX_RUNNER_MODE=branch_create
  git status --porcelain
  git checkout -b <branch>
  git status --porcelain
  ```
  If the initial status is dirty, it saves `git_status_before.txt` and stops. If branch creation fails, for example because the branch already exists, it saves stdout, stderr, and exit code artifacts and stops. If branch creation succeeds, it saves branch artifacts and prepares `run_codex_command.txt` and `run_codex.sh`. It still does not run Codex CLI, run `run_codex.sh`, commit, push, create PRs, or deploy.
- Codex run mode executes Codex CLI after a clean git check and branch creation:
  ```text
  PDLC_CODEX_RUNNER_MODE=codex_run
  <codex_bin> exec -C <project_local_path> - < <workspace>/codex_prompt.md
  ```
  The Codex subprocess uses `shell=False`, non-interactive `codex exec`, stdin from `codex_prompt.md`, and a configurable timeout (`PDLC_CODEX_TIMEOUT_SECONDS`, default `900`). The top-level interactive `codex` command must not be used for this path because it expects a terminal. After Codex exits, the runner saves `git diff`, `git diff --stat`, runs project test commands, and writes test/developer reports. It still does not run `run_codex.sh`, commit, push, create PRs, or deploy.
- Task UI is state-aware after Codex execution. If `codex_exit_code.txt` is `0`, `diff.patch` is non-empty, and `test_report.md` contains only passing exit codes, `/task`, `/prompt`, task details, and diff views show post-run controls instead of another Run Codex button.
- After successful `codex_run`, Telegram shows:
  ```text
  🔍 Diff
  🧪 Тесты
  ✅ Коммит
  🧹 Откат
  ```
- `Show diff` reads the task artifact `diff.patch` and displays it in Telegram, truncated when needed. If the patch is missing, the bot falls back to available artifact context.
- `Run tests again` is a placeholder and currently responds `Повторный запуск тестов пока не реализован.`
- `Commit changes` never commits directly. It first shows a confirmation button. Confirm commit:
  - reads the current git branch with `git branch --show-current`;
  - requires the current branch to match the task `branch_name.txt`;
  - requires the branch to match `agent/TASK-*`;
  - runs `git status --porcelain`, blocks protected paths, and stages allowed files explicitly;
  - runs `git commit -m "TASK-XXXX: <short task title>"`.
- Push is not part of commit. After a successful commit, Telegram shows a separate `📤 Push branch` button. Push is disabled by default with `PDLC_ENABLE_GIT_PUSH=false`. When enabled with `PDLC_ENABLE_GIT_PUSH=true`, push still requires confirmation and runs:
  ```text
  git push -u origin <branch>
  ```
- `Discard changes` never discards directly. It first shows a confirmation button. Confirm discard:
  - requires the current branch to match the task `branch_name.txt`;
  - requires the branch to match `agent/TASK-*`;
  - runs `git reset --hard`;
  - runs `git checkout main`.
- Never run Codex automatically when a task is created.
- Run only after an explicit user click.
- Do not commit without explicit confirm.
- Do not push without explicit confirm after commit.
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
- `branch_create_stdout.txt`
- `branch_create_stderr.txt`
- `branch_create_exit_code.txt`
- `git_status_after_branch.txt`
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

- `🔍 Diff`
- `🧪 Тесты`
- `✅ Коммит`
- `🧹 Откат`

After confirmed commit succeeds:

- `📤 Push branch`

## Implementation plan

1. Config flag + disabled button. Done.
2. Runner skeleton without Codex execution: prepare command only. Started with `run_codex_command.txt` and `run_codex.sh`.
3. Branch preparation without branch creation. Started with `branch_name.txt` and `git_status_before.txt` placeholder.
4. Checked git status collection without Codex execution. Started with `git_check`.
5. Branch creation only after explicit approval. Started with `branch_create`.
6. Actual Codex CLI execution. Started with `codex_run`.
7. Logs/artifacts capture. Started with `codex_stdout.log`, `codex_stderr.log`, `codex_exit_code.txt`, `diff.patch`, `test_report.md`, and `developer_report.md`.
8. Test runner. Started with configured project commands and fallback commands.
9. Telegram report. Started with post-run controls for show diff, confirmed commit, separate confirmed push, and confirmed discard.
10. Fix loop.
