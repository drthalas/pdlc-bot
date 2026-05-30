from __future__ import annotations

import json
import os
import shlex
from dataclasses import dataclass
from pathlib import Path

from app.task_store import TaskRecord


DEFAULT_CODEX_BIN = "/opt/homebrew/bin/codex"
DEFAULT_CODEX_RUNNER_MODE = "disabled"
PREPARE_COMMAND_FILENAME = "run_codex_command.txt"
PREPARE_SCRIPT_FILENAME = "run_codex.sh"


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


def write_codex_prepare_artifacts(task: TaskRecord) -> CodexPrepareResult:
    workspace_path = Path(task.workspace_path)
    workspace_path.mkdir(parents=True, exist_ok=True)
    command = build_codex_prepare_command(task)
    command_path = workspace_path / PREPARE_COMMAND_FILENAME
    script_path = workspace_path / PREPARE_SCRIPT_FILENAME

    command_path.write_text(f"{command}\n", encoding="utf-8")
    script_path.write_text(
        "\n".join(
            [
                "#!/usr/bin/env bash",
                "set -euo pipefail",
                "",
                "# Prepared by pdlc-bot Codex Runner prepare mode.",
                "# No command was executed by the bot.",
                command,
                "",
            ]
        ),
        encoding="utf-8",
    )
    script_path.chmod(script_path.stat().st_mode | 0o111)
    return CodexPrepareResult(command=command, command_path=command_path, script_path=script_path)


def build_codex_prepare_message(task: TaskRecord, result: CodexPrepareResult) -> str:
    return (
        "Codex Runner prepare mode. No command was executed.\n\n"
        f"Task: {task.task_id}\n"
        f"Script: {result.script_path}\n"
        f"Command: {result.command_path}"
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
    if mode == "prepare":
        return build_codex_prepare_message(task, write_codex_prepare_artifacts(task))

    if not is_codex_runner_enabled():
        return build_codex_runner_disabled_message(task.task_id)

    if mode in {"dry-run", "dry_run"}:
        return build_codex_dry_run_message(task)

    return build_codex_runner_disabled_message(task.task_id)
