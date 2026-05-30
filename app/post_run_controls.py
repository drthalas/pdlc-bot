from __future__ import annotations

import json
import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.task_store import TaskRecord


GIT_ACTION_TIMEOUT_SECONDS = 30
SAFE_AGENT_BRANCH_RE = re.compile(r"^agent/TASK-\d{4}(?:-.+)?$")
TASK_RESULT_READY_FOR_POST_RUN_ACTIONS = "ready_for_post_run_actions"
TASK_RESULT_COMMITTED = "committed"
TASK_RESULT_RUNNING = "running"
TASK_RESULT_PROMPT_READY = "prompt_ready"
SECRET_NAME_RE = re.compile(r"(?:^|[-_.])(secret|token|key)(?:[-_.]|$)", re.IGNORECASE)
EXPLICITLY_ALLOWED_SECRET_PATHS = {
    "tests/test_post_run_controls.py",
    "docs/CODEX_RUNNER_V0.md",
    "README.md",
}


@dataclass(frozen=True)
class PostRunActionResult:
    ok: bool
    message: str
    branch_name: str | None = None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _task_workspace(task: TaskRecord) -> Path:
    return Path(task.workspace_path)


def _load_project_local_path(task: TaskRecord) -> str | None:
    project_path = _task_workspace(task) / "project.json"
    try:
        payload = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    local_path = payload.get("local_path") if isinstance(payload, dict) else None
    return local_path.strip() if isinstance(local_path, str) and local_path.strip() else None


def _load_branch_name(task: TaskRecord) -> str | None:
    branch_name = _read_text(_task_workspace(task) / "branch_name.txt").strip()
    return branch_name or None


def is_safe_agent_branch(branch_name: str | None) -> bool:
    return branch_name is not None and SAFE_AGENT_BRANCH_RE.fullmatch(branch_name) is not None


def _codex_exit_code_is_zero(task: TaskRecord) -> bool:
    return _read_text(_task_workspace(task) / "codex_exit_code.txt").strip() == "0"


def _diff_exists(task: TaskRecord) -> bool:
    return bool(_read_text(_task_workspace(task) / "diff.patch").strip())


def _tests_passed(task: TaskRecord) -> bool:
    report = _read_text(_task_workspace(task) / "test_report.md")
    exit_codes = re.findall(r"^Exit code: (\d+)$", report, flags=re.MULTILINE)
    return bool(exit_codes) and all(code == "0" for code in exit_codes)


def should_show_post_run_controls(task: TaskRecord) -> bool:
    return _codex_exit_code_is_zero(task) and _diff_exists(task) and _tests_passed(task)


def task_result_state(task: TaskRecord) -> str:
    if task.status == "committed":
        return TASK_RESULT_COMMITTED
    if task.status in {"coding", "codex_running", "testing"}:
        return TASK_RESULT_RUNNING
    if should_show_post_run_controls(task):
        return TASK_RESULT_READY_FOR_POST_RUN_ACTIONS
    return TASK_RESULT_PROMPT_READY


def is_git_push_enabled() -> bool:
    return os.getenv("PDLC_ENABLE_GIT_PUSH", "false").strip().lower() in {"1", "true", "yes", "on"}


def build_show_diff_message(task: TaskRecord, max_chars: int = 3500) -> str:
    workspace = _task_workspace(task)
    diff = _read_text(workspace / "diff.patch").strip()
    if diff:
        if len(diff) > max_chars:
            diff = f"{diff[:max_chars]}\n\n... truncated. Full diff: {workspace / 'diff.patch'}"
        return f"Diff for {task.task_id}:\n\n```diff\n{diff}\n```"

    developer_report = _read_text(workspace / "developer_report.md").strip()
    if developer_report:
        diff_stat_match = re.search(r"## Diff Stat\s+```text\s+(.*?)\s+```", developer_report, flags=re.DOTALL)
        if diff_stat_match is not None:
            diff_stat = diff_stat_match.group(1).strip() or "no diff"
            return f"No diff.patch content found for {task.task_id}. Diff stat:\n\n```text\n{diff_stat[:max_chars]}\n```"
        return f"No diff.patch content found for {task.task_id}. Developer report:\n\n{developer_report[:max_chars]}"
    return f"No diff artifact found for {task.task_id}."


def build_commit_message(task: TaskRecord, max_title_chars: int = 50) -> str:
    title = "task"
    for line in _read_text(_task_workspace(task) / "input.md").splitlines():
        normalized = " ".join(line.strip().split())
        if normalized:
            title = normalized
            break
    if len(title) > max_title_chars:
        title = f"{title[: max_title_chars - 3].rstrip()}..."
    return f"{task.task_id}: {title}"


def _run_git(
    command: list[str],
    project_local_path: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> subprocess.CompletedProcess[str]:
    return runner(
        command,
        cwd=project_local_path,
        capture_output=True,
        text=True,
        timeout=GIT_ACTION_TIMEOUT_SECONDS,
        check=False,
    )


def _parse_porcelain_path(line: str) -> str | None:
    if not line.strip():
        return None
    path = line[3:]
    if " -> " in path:
        path = path.split(" -> ", 1)[1]
    return path.strip().strip('"') or None


def is_denied_commit_path(path: str) -> bool:
    normalized = path.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in {".env", "config/projects.yaml"}:
        return True
    if normalized.startswith(".env."):
        return True
    if normalized.startswith("tasks/"):
        return True
    if normalized.endswith(".sqlite3"):
        return True
    name = Path(normalized).name
    if SECRET_NAME_RE.search(name) and normalized not in EXPLICITLY_ALLOWED_SECRET_PATHS:
        return True
    return False


def changed_files_for_commit(
    project_local_path: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[list[str], PostRunActionResult | None]:
    result = _run_git(["git", "status", "--porcelain"], project_local_path, runner)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        return [], PostRunActionResult(False, f"git status failed: {detail}")

    files = [path for line in result.stdout.splitlines() if (path := _parse_porcelain_path(line))]
    denied = [path for path in files if is_denied_commit_path(path)]
    if denied:
        return [], PostRunActionResult(False, "Refusing commit because protected files are changed: " + ", ".join(denied))
    if not files:
        return [], PostRunActionResult(False, "No changed files to commit.")
    return files, None


def _current_branch(
    project_local_path: str,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> PostRunActionResult:
    result = _run_git(["git", "branch", "--show-current"], project_local_path, runner)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        return PostRunActionResult(False, f"Could not read current branch: {detail}")
    branch_name = result.stdout.strip()
    if not is_safe_agent_branch(branch_name):
        return PostRunActionResult(False, f"Refusing git action outside agent/TASK-* branch. Current branch: {branch_name or 'unknown'}")
    return PostRunActionResult(True, "Current branch is safe.", branch_name=branch_name)


def _validate_project_and_branch(
    task: TaskRecord,
    runner: Callable[..., subprocess.CompletedProcess[str]],
) -> tuple[str | None, str | None, PostRunActionResult | None]:
    project_local_path = _load_project_local_path(task)
    if project_local_path is None:
        return None, None, PostRunActionResult(False, f"Project local_path not found for {task.task_id}.")

    artifact_branch = _load_branch_name(task)
    if not is_safe_agent_branch(artifact_branch):
        return project_local_path, None, PostRunActionResult(False, "Stored branch_name.txt is missing or not an agent/TASK-* branch.")

    branch_result = _current_branch(project_local_path, runner)
    if not branch_result.ok:
        return project_local_path, artifact_branch, branch_result
    if branch_result.branch_name != artifact_branch:
        return project_local_path, artifact_branch, PostRunActionResult(
            False,
            f"Refusing git action because current branch is {branch_result.branch_name}, expected {artifact_branch}.",
        )
    return project_local_path, artifact_branch, None


def commit_task_changes(
    task: TaskRecord,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PostRunActionResult:
    project_local_path, branch_name, error = _validate_project_and_branch(task, runner)
    if error is not None:
        return error
    assert project_local_path is not None
    assert branch_name is not None

    changed_files, changed_error = changed_files_for_commit(project_local_path, runner)
    if changed_error is not None:
        return PostRunActionResult(False, changed_error.message, branch_name=branch_name)

    add_result = _run_git(["git", "add", *changed_files], project_local_path, runner)
    if add_result.returncode != 0:
        detail = add_result.stderr.strip() or add_result.stdout.strip() or f"exit code {add_result.returncode}"
        return PostRunActionResult(False, f"git add failed: {detail}", branch_name=branch_name)

    message = build_commit_message(task)
    commit_result = _run_git(["git", "commit", "-m", message], project_local_path, runner)
    if commit_result.returncode != 0:
        detail = commit_result.stderr.strip() or commit_result.stdout.strip() or f"exit code {commit_result.returncode}"
        return PostRunActionResult(False, f"git commit failed: {detail}", branch_name=branch_name)

    return PostRunActionResult(True, f"Committed local changes on {branch_name}.\nMessage: {message}", branch_name=branch_name)


def push_task_branch(
    task: TaskRecord,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PostRunActionResult:
    if not is_git_push_enabled():
        return PostRunActionResult(False, "Push is disabled by configuration.")

    project_local_path, branch_name, error = _validate_project_and_branch(task, runner)
    if error is not None:
        return error
    assert project_local_path is not None
    assert branch_name is not None

    push_result = _run_git(["git", "push", "-u", "origin", branch_name], project_local_path, runner)
    if push_result.returncode != 0:
        detail = push_result.stderr.strip() or push_result.stdout.strip() or f"exit code {push_result.returncode}"
        return PostRunActionResult(False, f"git push failed: {detail}", branch_name=branch_name)
    return PostRunActionResult(True, f"Pushed branch {branch_name}.", branch_name=branch_name)


def discard_task_changes(
    task: TaskRecord,
    runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
) -> PostRunActionResult:
    project_local_path, branch_name, error = _validate_project_and_branch(task, runner)
    if error is not None:
        return error
    assert project_local_path is not None
    assert branch_name is not None

    reset_result = _run_git(["git", "reset", "--hard"], project_local_path, runner)
    if reset_result.returncode != 0:
        detail = reset_result.stderr.strip() or reset_result.stdout.strip() or f"exit code {reset_result.returncode}"
        return PostRunActionResult(False, f"git reset --hard failed: {detail}", branch_name=branch_name)

    checkout_result = _run_git(["git", "checkout", "main"], project_local_path, runner)
    if checkout_result.returncode != 0:
        detail = checkout_result.stderr.strip() or checkout_result.stdout.strip() or f"exit code {checkout_result.returncode}"
        return PostRunActionResult(False, f"git checkout main failed: {detail}", branch_name=branch_name)

    return PostRunActionResult(True, f"Discarded local changes from {branch_name} and checked out main.", branch_name=branch_name)
