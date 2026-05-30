import shlex
from pathlib import Path

from app.codex_runner import (
    build_branch_name,
    build_codex_branch_prepare_message,
    build_codex_prepare_command,
    build_codex_prepare_message,
    build_codex_dry_run_command,
    build_codex_runner_disabled_message,
    get_codex_bin_path,
    get_codex_runner_mode,
    is_git_status_clean,
    is_codex_runner_enabled,
    write_codex_branch_prepare_artifacts,
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


def test_codex_runner_branch_prepare_mode_is_recognized(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_RUNNER_MODE", "branch_prepare")

    assert get_codex_runner_mode() == "branch_prepare"


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


def test_branch_name_is_safe_and_contains_task_id(tmp_path):
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )

    branch_name = build_branch_name(task, "Add persistent menu!!!")

    assert branch_name == "agent/TASK-0007-add-persistent-menu"
    assert "TASK-0007" in branch_name


def test_git_status_clean_helper_covers_dirty_tree():
    assert is_git_status_clean("") is True
    assert is_git_status_clean("On branch main\nnothing to commit, working tree clean") is True
    assert is_git_status_clean(" M app/main.py\n?? scratch.txt") is False


def test_codex_branch_prepare_artifacts_are_created(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "input.md").write_text("Add persistent menu\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("Do the task.\n", encoding="utf-8")
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )

    result = write_codex_branch_prepare_artifacts(task)

    assert result.branch_name == "agent/TASK-0007-add-persistent-menu"
    assert result.git_status_path == workspace / "git_status_before.txt"
    assert result.branch_name_path == workspace / "branch_name.txt"
    assert result.command_path == workspace / "run_codex_command.txt"
    assert result.script_path == workspace / "run_codex.sh"
    assert result.branch_name_path.read_text(encoding="utf-8") == f"{result.branch_name}\n"
    assert "Git status was not executed" in result.git_status_path.read_text(encoding="utf-8")
    assert result.command_path.read_text(encoding="utf-8") == f"{result.command}\n"

    script = result.script_path.read_text(encoding="utf-8")
    assert "branch_prepare mode" in script
    assert "No branch was created by the bot." in script
    assert "No command was executed by the bot." in script
    assert result.branch_name in script
    assert result.script_path.stat().st_mode & 0o111


def test_codex_branch_prepare_message_reports_no_branch_or_command(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "input.md").write_text("Add persistent menu\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("Do the task.\n", encoding="utf-8")
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )
    result = write_codex_branch_prepare_artifacts(task)

    message = build_codex_branch_prepare_message(task, result)

    assert "Codex Runner branch_prepare mode" in message
    assert "No branch was created" in message
    assert "No command was executed" in message
    assert "agent/TASK-0007-add-persistent-menu" in message
    assert "git_status_before.txt" in message
    assert "branch_name.txt" in message
