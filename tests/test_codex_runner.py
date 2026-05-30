from app.codex_runner import (
    build_codex_dry_run_command,
    build_codex_runner_disabled_message,
    get_codex_bin_path,
    get_codex_runner_mode,
    is_codex_runner_enabled,
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

    assert build_codex_dry_run_command(task) == "/custom/codex < tasks/TASK-0007/codex_prompt.md"
