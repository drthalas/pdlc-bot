import shlex
from pathlib import Path

from app.codex_runner import (
    build_codex_prepare_command,
    build_codex_prepare_message,
    build_codex_dry_run_command,
    build_codex_runner_disabled_message,
    get_codex_bin_path,
    get_codex_runner_mode,
    is_codex_runner_enabled,
    write_codex_prepare_artifacts,
)
from app.task_store import TaskRecord


def test_codex_runner_disabled_by_default(monkeypatch):
    monkeypatch.delenv("PDLC_ENABLE_CODEX_RUNNER", raising=False)
    monkeypatch.delenv("PDLC_CODEX_RUNNER_MODE", raising=False)
    monkeypatch.delenv("PDLC_CODEX_BIN", raising=False)

    assert is_codex_runner_enabled() is False
    assert get_codex_runner_mode() == "disabled"
    assert get_codex_bin_path() == "/opt/homebrew/bin/codex"


def test_codex_runner_disabled_message_contains_safe_context():
    message = build_codex_runner_disabled_message("TASK-0007")

    assert "Codex Runner is disabled" in message
    assert "prompt/artifact mode" in message
    assert "TASK-0007" in message


def test_codex_dry_run_command_is_only_text(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path="tasks/TASK-0007",
        created_at="2026-05-30T00:00:00+00:00",
    )

    prompt_path = Path("tasks/TASK-0007/codex_prompt.md").resolve()
    assert build_codex_dry_run_command(task) == f"cd . && /custom/codex < {shlex.quote(str(prompt_path))}"


def test_codex_runner_prepare_mode_is_recognized(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_RUNNER_MODE", "prepare")

    assert get_codex_runner_mode() == "prepare"


def test_codex_prepare_command_uses_project_path_and_prompt(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )

    command = build_codex_prepare_command(task, project_local_path="/tmp/project path")

    assert command == f"cd '/tmp/project path' && /custom/codex < {workspace}/codex_prompt.md"


def test_codex_prepare_artifacts_are_created(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "codex_prompt.md").write_text("Do the task.\n", encoding="utf-8")
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )

    result = write_codex_prepare_artifacts(task)

    assert result.command_path == workspace / "run_codex_command.txt"
    assert result.script_path == workspace / "run_codex.sh"
    assert result.command == f"cd /tmp/project && /custom/codex < {workspace}/codex_prompt.md"
    assert result.command_path.read_text(encoding="utf-8") == f"{result.command}\n"

    script = result.script_path.read_text(encoding="utf-8")
    assert script.startswith("#!/usr/bin/env bash\nset -euo pipefail")
    assert "No command was executed by the bot." in script
    assert result.command in script
    assert result.script_path.stat().st_mode & 0o111


def test_codex_prepare_message_says_no_command_was_executed(tmp_path):
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )
    result = write_codex_prepare_artifacts(task)

    message = build_codex_prepare_message(task, result)

    assert "Codex Runner prepare mode" in message
    assert "No command was executed" in message
    assert "TASK-0007" in message
    assert str(result.script_path) in message
