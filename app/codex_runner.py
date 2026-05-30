from __future__ import annotations

import os

from app.task_store import TaskRecord


DEFAULT_CODEX_BIN = "/opt/homebrew/bin/codex"
DEFAULT_CODEX_RUNNER_MODE = "disabled"


def is_codex_runner_enabled() -> bool:
    return os.getenv("PDLC_ENABLE_CODEX_RUNNER", "false").strip().lower() in {"1", "true", "yes", "on"}


def get_codex_runner_mode() -> str:
    return os.getenv("PDLC_CODEX_RUNNER_MODE", DEFAULT_CODEX_RUNNER_MODE).strip().lower() or DEFAULT_CODEX_RUNNER_MODE


def get_codex_bin_path() -> str:
    return os.getenv("PDLC_CODEX_BIN", DEFAULT_CODEX_BIN).strip() or DEFAULT_CODEX_BIN


def build_codex_runner_disabled_message(task_id: str) -> str:
    return (
        "Codex Runner is disabled.\n\n"
        "Current mode: prompt/artifact mode.\n"
        "The task is ready for manual Codex usage.\n\n"
        f"Task: {task_id}\n"
        "Prompt: available via Codex prompt button."
    )


def build_codex_dry_run_command(task: TaskRecord) -> str:
    return f"{get_codex_bin_path()} < {task.workspace_path}/codex_prompt.md"


def build_codex_dry_run_message(task: TaskRecord) -> str:
    return (
        "Codex Runner dry-run.\n\n"
        "Prepared command:\n"
        f"{build_codex_dry_run_command(task)}\n\n"
        "No command was executed."
    )


def build_codex_runner_response(task: TaskRecord) -> str:
    if not is_codex_runner_enabled():
        return build_codex_runner_disabled_message(task.task_id)

    if get_codex_runner_mode() in {"dry-run", "dry_run", "prepare"}:
        return build_codex_dry_run_message(task)

    return build_codex_runner_disabled_message(task.task_id)
