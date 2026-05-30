from __future__ import annotations

import json
import os
import re
import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.task_store import TaskRecord


DEFAULT_CODEX_BIN = "/opt/homebrew/bin/codex"
DEFAULT_CODEX_RUNNER_MODE = "disabled"
PREPARE_COMMAND_FILENAME = "run_codex_command.txt"
PREPARE_SCRIPT_FILENAME = "run_codex.sh"
GIT_STATUS_BEFORE_FILENAME = "git_status_before.txt"
BRANCH_NAME_FILENAME = "branch_name.txt"
GIT_STATUS_TIMEOUT_SECONDS = 10
BRANCH_CREATE_STDOUT_FILENAME = "branch_create_stdout.txt"
BRANCH_CREATE_STDERR_FILENAME = "branch_create_stderr.txt"
BRANCH_CREATE_EXIT_CODE_FILENAME = "branch_create_exit_code.txt"
GIT_STATUS_AFTER_BRANCH_FILENAME = "git_status_after_branch.txt"


def is_codex_runner_enabled() -> bool:
    return os.getenv("PDLC_ENABLE_CODEX_RUNNER", "false").strip().lower() in {"1", "true", "yes", "on"}


def get_codex_runner_mode() -> str:
    return os.getenv("PDLC_CODEX_RUNNER_MODE", DEFAULT_CODEX_RUNNER_MODE).strip().lower() or DEFAULT_CODEX_RUNNER_MODE


def get_codex_bin_path() -> str:
    return os.getenv("PDLC_CODEX_BIN", DEFAULT_CODEX_BIN).strip() or DEFAULT_CODEX_BIN


@dataclass(frozen=True)
class CodexPrepareResult:
    command: str
    command_path: Path
    script_path: Path


@dataclass(frozen=True)
class CodexBranchPrepareResult(CodexPrepareResult):
    branch_name: str
    branch_name_path: Path
    git_status_path: Path


@dataclass(frozen=True)
class CodexGitCheckResult:
    is_clean: bool
    git_status: str
    git_status_path: Path
    branch_name: str | None = None
    branch_name_path: Path | None = None
    command_path: Path | None = None
    script_path: Path | None = None


@dataclass(frozen=True)
class GitCommandResult:
    stdout: str
    stderr: str
    exit_code: int


@dataclass(frozen=True)
class CodexBranchCreateResult:
    is_clean: bool
    branch_created: bool
    git_status_before: str
    git_status_before_path: Path
    branch_name: str | None = None
    branch_name_path: Path | None = None
    branch_stdout_path: Path | None = None
    branch_stderr_path: Path | None = None
    branch_exit_code_path: Path | None = None
    git_status_after_path: Path | None = None
    command_path: Path | None = None
    script_path: Path | None = None
    error_message: str | None = None


def build_codex_runner_disabled_message(task_id: str) -> str:
    return (
        "Codex Runner is disabled.\n\n"
        "Current mode: prompt/artifact mode.\n"
        "The task is ready for manual Codex usage.\n\n"
        f"Task: {task_id}\n"
        "Prompt: available via Codex prompt button."
    )


def _load_project_local_path(task: TaskRecord) -> str | None:
    project_path = Path(task.workspace_path) / "project.json"
    if not project_path.exists():
        return None

    try:
        payload = json.loads(project_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    local_path = payload.get("local_path")
    if isinstance(local_path, str) and local_path.strip():
        return local_path.strip()
    return None


def build_codex_prepare_command(task: TaskRecord, project_local_path: str | None = None) -> str:
    workspace_path = Path(task.workspace_path).resolve()
    prompt_path = workspace_path / "codex_prompt.md"
    project_path = project_local_path or _load_project_local_path(task) or "."
    return (
        f"cd {shlex.quote(project_path)} && "
        f"{shlex.quote(get_codex_bin_path())} < {shlex.quote(str(prompt_path))}"
    )


def _write_prepare_command_and_script(
    workspace_path: Path,
    command: str,
    script_comments: list[str],
) -> CodexPrepareResult:
    command_path = workspace_path / PREPARE_COMMAND_FILENAME
    script_path = workspace_path / PREPARE_SCRIPT_FILENAME

    command_path.write_text(f"{command}\n", encoding="utf-8")
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                *script_comments,
                command,
                "",
            ]
        ),
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | 0o111)
    return CodexPrepareResult(command=command, command_path=command_path, script_path=script_path)


def write_codex_prepare_artifacts(task: TaskRecord) -> CodexPrepareResult:
    workspace_path = Path(task.workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    command = build_codex_prepare_command(task)
    return _write_prepare_command_and_script(
        workspace_path,
        command,
        [
            "# Prepared by pdlc-bot Codex Runner prepare mode.",
            "# No command was executed by the bot.",
        ],
    )


def _read_task_input(task: TaskRecord) -> str:
    input_path = Path(task.workspace_path) / "input.md"
    if not input_path.exists():
        return ""
    try:
        return input_path.read_text(encoding="utf-8")
    except OSError:
        return ""


def build_branch_slug(text: str, fallback: str = "task") -> str:
    normalized = text.strip().lower()
    slug = re.sub(r"[^a-z0-9]+", "-", normalized).strip("-")
    slug = re.sub(r"-{2,}", "-", slug)
    if not slug:
        return fallback
    return slug[:48].strip("-") or fallback


def build_branch_name(task: TaskRecord, source_text: str | None = None) -> str:
    slug_source = source_text if source_text is not None else _read_task_input(task)
    return f"agent/{task.task_id}-{build_branch_slug(slug_source)}"


def is_git_status_clean(status_text: str) -> bool:
    cleaned = status_text.strip()
    if not cleaned:
        return True
    lowered = cleaned.lower()
    return "nothing to commit, working tree clean" in lowered


def read_git_status_porcelain(project_local_path: str, timeout: int = GIT_STATUS_TIMEOUT_SECONDS) -> str:
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=project_local_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"git status timed out after {timeout} seconds") from error
    except OSError as error:
        raise RuntimeError(f"git status failed to start: {error}") from error

    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit code {result.returncode}"
        raise RuntimeError(f"git status failed: {detail}")

    return result.stdout


def create_git_branch(
    project_local_path: str,
    branch_name: str,
    timeout: int = GIT_STATUS_TIMEOUT_SECONDS,
) -> GitCommandResult:
    try:
        result = subprocess.run(
            ["git", "checkout", "-b", branch_name],
            cwd=project_local_path,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired as error:
        raise RuntimeError(f"git checkout -b timed out after {timeout} seconds") from error
    except OSError as error:
        raise RuntimeError(f"git checkout -b failed to start: {error}") from error

    return GitCommandResult(stdout=result.stdout, stderr=result.stderr, exit_code=result.returncode)


def build_git_status_placeholder(project_local_path: str) -> str:
    return (
        "Git status was not executed by pdlc-bot in branch_prepare mode.\n\n"
        "Reason: subprocess execution is intentionally disabled for this stage.\n"
        "TODO: collect `git status --short --branch` before actual branch creation.\n\n"
        f"Target repo: {project_local_path}\n"
    )


def write_codex_git_check_artifacts(
    task: TaskRecord,
    git_status_reader: Callable[[str], str] = read_git_status_porcelain,
) -> CodexGitCheckResult:
    project_local_path = _load_project_local_path(task)
    if project_local_path is None:
        raise ValueError(f"Project local_path not found for {task.task_id}.")

    workspace_path = Path(task.workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    git_status = git_status_reader(project_local_path)
    git_status_path = workspace_path / GIT_STATUS_BEFORE_FILENAME
    git_status_path.write_text(git_status, encoding="utf-8")

    if not is_git_status_clean(git_status):
        return CodexGitCheckResult(
            is_clean=False,
            git_status=git_status,
            git_status_path=git_status_path,
        )

    branch_name = build_branch_name(task)
    command = build_codex_prepare_command(task, project_local_path=project_local_path)
    prepare_result = _write_prepare_command_and_script(
        workspace_path,
        command,
        [
            "# Prepared by pdlc-bot Codex Runner git_check mode.",
            "# Working tree was clean when checked by the bot.",
            "# No branch was created by the bot.",
            "# No command was executed by the bot.",
            f"# Intended branch: {branch_name}",
        ],
    )
    branch_name_path = workspace_path / BRANCH_NAME_FILENAME
    branch_name_path.write_text(f"{branch_name}\n", encoding="utf-8")

    return CodexGitCheckResult(
        is_clean=True,
        git_status=git_status,
        git_status_path=git_status_path,
        branch_name=branch_name,
        branch_name_path=branch_name_path,
        command_path=prepare_result.command_path,
        script_path=prepare_result.script_path,
    )


def write_codex_branch_create_artifacts(
    task: TaskRecord,
    git_status_reader: Callable[[str], str] = read_git_status_porcelain,
    branch_creator: Callable[[str, str], GitCommandResult] = create_git_branch,
) -> CodexBranchCreateResult:
    project_local_path = _load_project_local_path(task)
    if project_local_path is None:
        raise ValueError(f"Project local_path not found for {task.task_id}.")

    workspace_path = Path(task.workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)

    git_status_before = git_status_reader(project_local_path)
    git_status_before_path = workspace_path / GIT_STATUS_BEFORE_FILENAME
    git_status_before_path.write_text(git_status_before, encoding="utf-8")

    if not is_git_status_clean(git_status_before):
        return CodexBranchCreateResult(
            is_clean=False,
            branch_created=False,
            git_status_before=git_status_before,
            git_status_before_path=git_status_before_path,
            error_message="Working tree is dirty.",
        )

    branch_name = build_branch_name(task)
    branch_result = branch_creator(project_local_path, branch_name)

    branch_name_path = workspace_path / BRANCH_NAME_FILENAME
    branch_stdout_path = workspace_path / BRANCH_CREATE_STDOUT_FILENAME
    branch_stderr_path = workspace_path / BRANCH_CREATE_STDERR_FILENAME
    branch_exit_code_path = workspace_path / BRANCH_CREATE_EXIT_CODE_FILENAME

    branch_name_path.write_text(f"{branch_name}\n", encoding="utf-8")
    branch_stdout_path.write_text(branch_result.stdout, encoding="utf-8")
    branch_stderr_path.write_text(branch_result.stderr, encoding="utf-8")
    branch_exit_code_path.write_text(f"{branch_result.exit_code}\n", encoding="utf-8")

    if branch_result.exit_code != 0:
        detail = branch_result.stderr.strip() or branch_result.stdout.strip() or f"exit code {branch_result.exit_code}"
        return CodexBranchCreateResult(
            is_clean=True,
            branch_created=False,
            git_status_before=git_status_before,
            git_status_before_path=git_status_before_path,
            branch_name=branch_name,
            branch_name_path=branch_name_path,
            branch_stdout_path=branch_stdout_path,
            branch_stderr_path=branch_stderr_path,
            branch_exit_code_path=branch_exit_code_path,
            error_message=f"Branch was not created: {detail}",
        )

    git_status_after = git_status_reader(project_local_path)
    git_status_after_path = workspace_path / GIT_STATUS_AFTER_BRANCH_FILENAME
    git_status_after_path.write_text(git_status_after, encoding="utf-8")

    command = build_codex_prepare_command(task, project_local_path=project_local_path)
    prepare_result = _write_prepare_command_and_script(
        workspace_path,
        command,
        [
            "# Prepared by pdlc-bot Codex Runner branch_create mode.",
            "# Branch was created by the bot.",
            "# No Codex command was executed by the bot.",
            "# No commit, push, PR, or deploy was performed by the bot.",
            f"# Branch: {branch_name}",
        ],
    )

    return CodexBranchCreateResult(
        is_clean=True,
        branch_created=True,
        git_status_before=git_status_before,
        git_status_before_path=git_status_before_path,
        branch_name=branch_name,
        branch_name_path=branch_name_path,
        branch_stdout_path=branch_stdout_path,
        branch_stderr_path=branch_stderr_path,
        branch_exit_code_path=branch_exit_code_path,
        git_status_after_path=git_status_after_path,
        command_path=prepare_result.command_path,
        script_path=prepare_result.script_path,
    )


def write_codex_branch_prepare_artifacts(task: TaskRecord) -> CodexBranchPrepareResult:
    project_local_path = _load_project_local_path(task)
    if project_local_path is None:
        raise ValueError(f"Project local_path not found for {task.task_id}.")

    workspace_path = Path(task.workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    branch_name = build_branch_name(task)
    command = build_codex_prepare_command(task, project_local_path=project_local_path)
    prepare_result = _write_prepare_command_and_script(
        workspace_path,
        command,
        [
            "# Prepared by pdlc-bot Codex Runner branch_prepare mode.",
            "# No branch was created by the bot.",
            "# No command was executed by the bot.",
            f"# Intended branch: {branch_name}",
        ],
    )

    branch_name_path = workspace_path / BRANCH_NAME_FILENAME
    git_status_path = workspace_path / GIT_STATUS_BEFORE_FILENAME
    branch_name_path.write_text(f"{branch_name}\n", encoding="utf-8")
    git_status_path.write_text(build_git_status_placeholder(project_local_path), encoding="utf-8")

    return CodexBranchPrepareResult(
        command=prepare_result.command,
        command_path=prepare_result.command_path,
        script_path=prepare_result.script_path,
        branch_name=branch_name,
        branch_name_path=branch_name_path,
        git_status_path=git_status_path,
    )


def build_codex_prepare_message(task: TaskRecord, result: CodexPrepareResult) -> str:
    return (
        "Codex Runner prepare mode. No command was executed.\n\n"
        f"Task: {task.task_id}\n"
        f"Script: {result.script_path}\n"
        f"Command: {result.command_path}"
    )


def build_codex_branch_prepare_message(task: TaskRecord, result: CodexBranchPrepareResult) -> str:
    return (
        "Codex Runner branch_prepare mode.\n"
        "No branch was created.\n"
        "No command was executed.\n\n"
        f"Task: {task.task_id}\n"
        f"Branch: {result.branch_name}\n\n"
        "Artifacts:\n"
        f"- {result.git_status_path}\n"
        f"- {result.branch_name_path}\n"
        f"- {result.command_path}\n"
        f"- {result.script_path}"
    )


def build_codex_git_check_message(task: TaskRecord, result: CodexGitCheckResult) -> str:
    if not result.is_clean:
        return (
            "Codex Runner git_check mode.\n"
            "Working tree is dirty.\n"
            "No branch was created.\n"
            "No command was executed.\n\n"
            f"Task: {task.task_id}\n\n"
            "Artifacts:\n"
            f"- {result.git_status_path}"
        )

    return (
        "Codex Runner git_check mode. Working tree is clean.\n"
        "No branch was created.\n"
        "No command was executed.\n\n"
        f"Task: {task.task_id}\n"
        f"Branch: {result.branch_name}\n\n"
        "Artifacts:\n"
        f"- {result.git_status_path}\n"
        f"- {result.branch_name_path}\n"
        f"- {result.command_path}\n"
        f"- {result.script_path}"
    )


def build_codex_branch_create_message(task: TaskRecord, result: CodexBranchCreateResult) -> str:
    if not result.is_clean:
        return (
            "Codex Runner branch_create mode.\n"
            "Working tree is dirty.\n"
            "No branch was created.\n"
            "No Codex command was executed.\n"
            "No commit/push was performed.\n\n"
            f"Task: {task.task_id}\n\n"
            "Artifacts:\n"
            f"- {result.git_status_before_path}"
        )

    if not result.branch_created:
        return (
            "Codex Runner branch_create mode.\n"
            f"{result.error_message or 'Branch was not created.'}\n"
            "No Codex command was executed.\n"
            "No commit/push was performed.\n\n"
            f"Task: {task.task_id}\n"
            f"Branch: {result.branch_name}\n\n"
            "Artifacts:\n"
            f"- {result.git_status_before_path}\n"
            f"- {result.branch_name_path}\n"
            f"- {result.branch_stdout_path}\n"
            f"- {result.branch_stderr_path}\n"
            f"- {result.branch_exit_code_path}"
        )

    return (
        "Codex Runner branch_create mode.\n"
        f"Branch created: {result.branch_name}\n"
        "No Codex command was executed.\n"
        "No commit/push was performed.\n\n"
        f"Task: {task.task_id}\n\n"
        "Artifacts:\n"
        f"- {result.git_status_before_path}\n"
        f"- {result.branch_name_path}\n"
        f"- {result.branch_stdout_path}\n"
        f"- {result.branch_stderr_path}\n"
        f"- {result.branch_exit_code_path}\n"
        f"- {result.git_status_after_path}\n"
        f"- {result.command_path}\n"
        f"- {result.script_path}"
    )


def build_codex_dry_run_command(task: TaskRecord) -> str:
    return build_codex_prepare_command(task)


def build_codex_dry_run_message(task: TaskRecord) -> str:
    return (
        "Codex Runner dry-run.\n\n"
        "Prepared command:\n"
        f"{build_codex_dry_run_command(task)}\n\n"
        "No command was executed."
    )


def build_codex_runner_response(task: TaskRecord) -> str:
    mode = get_codex_runner_mode()
    if mode == "branch_create":
        try:
            return build_codex_branch_create_message(task, write_codex_branch_create_artifacts(task))
        except (RuntimeError, ValueError) as error:
            return f"Codex Runner branch_create mode cannot continue.\n\n{error}"

    if mode == "git_check":
        try:
            return build_codex_git_check_message(task, write_codex_git_check_artifacts(task))
        except (RuntimeError, ValueError) as error:
            return f"Codex Runner git_check mode cannot continue.\n\n{error}"

    if mode == "branch_prepare":
        try:
            return build_codex_branch_prepare_message(task, write_codex_branch_prepare_artifacts(task))
        except ValueError as error:
            return f"Codex Runner branch_prepare mode cannot continue.\n\n{error}"

    if mode == "prepare":
        return build_codex_prepare_message(task, write_codex_prepare_artifacts(task))

    if not is_codex_runner_enabled():
        return build_codex_runner_disabled_message(task.task_id)

    if mode in {"dry-run", "dry_run"}:
        return build_codex_dry_run_message(task)

    return build_codex_runner_disabled_message(task.task_id)
