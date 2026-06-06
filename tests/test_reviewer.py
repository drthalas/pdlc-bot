from pathlib import Path

from app.reviewer import (
    REVIEW_STATUS_APPROVED,
    REVIEW_STATUS_CHANGES_REQUESTED,
    build_review_report_message,
    is_sensitive_path,
    run_reviewer,
)
from app.task_store import TaskRecord


def make_task(workspace: Path, task_id: str = "TASK-0007") -> TaskRecord:
    workspace.mkdir(parents=True, exist_ok=True)
    return TaskRecord(task_id, "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")


def write_success_artifacts(workspace: Path, diff: str | None = None) -> None:
    (workspace / "codex_exit_code.txt").write_text("0\n", encoding="utf-8")
    (workspace / "test_report.md").write_text("Exit code: 0\n", encoding="utf-8")
    (workspace / "developer_report.md").write_text("No commit, push, PR, or deploy was performed.\n", encoding="utf-8")
    (workspace / "git_status_after.txt").write_text(" M app/telegram_ui.py\n", encoding="utf-8")
    (workspace / "diff.patch").write_text(
        diff
        or (
            "diff --git a/app/telegram_ui.py b/app/telegram_ui.py\n"
            "--- a/app/telegram_ui.py\n"
            "+++ b/app/telegram_ui.py\n"
            "@@\n"
            "+print('ok')\n"
        ),
        encoding="utf-8",
    )


def test_reviewer_approves_clean_successful_task(tmp_path):
    workspace = tmp_path / "TASK-0007"
    task = make_task(workspace)
    write_success_artifacts(workspace)

    result = run_reviewer(task)

    assert result.status == REVIEW_STATUS_APPROVED
    assert result.report_path == workspace / "review_report.md"
    report = result.report_path.read_text(encoding="utf-8")
    assert "Status: approved" in report
    assert "Codex exit code: passed" in report
    assert "Tests: passed" in report
    assert "Проверить, что пользовательские Telegram-тексты на русском." in report


def test_reviewer_changes_requested_on_codex_failure(tmp_path):
    workspace = tmp_path / "TASK-0007"
    task = make_task(workspace)
    write_success_artifacts(workspace)
    (workspace / "codex_exit_code.txt").write_text("2\n", encoding="utf-8")

    result = run_reviewer(task)

    assert result.status == REVIEW_STATUS_CHANGES_REQUESTED
    assert "Codex exit code is 2." in result.required_fixes


def test_reviewer_changes_requested_on_tests_failure(tmp_path):
    workspace = tmp_path / "TASK-0007"
    task = make_task(workspace)
    write_success_artifacts(workspace)
    (workspace / "test_report.md").write_text("Exit code: 1\nfailed\n", encoding="utf-8")

    result = run_reviewer(task)

    assert result.status == REVIEW_STATUS_CHANGES_REQUESTED
    assert "Fix failing or missing tests before commit." in result.required_fixes


def test_reviewer_changes_requested_on_sensitive_file_diff(tmp_path):
    sensitive_paths = [".env", "config/projects.yaml", "tasks/TASK-0001/input.md", "data/app.sqlite3"]
    for index, path in enumerate(sensitive_paths, start=1):
        workspace = tmp_path / f"TASK-{index:04d}"
        task = make_task(workspace, f"TASK-{index:04d}")
        write_success_artifacts(
            workspace,
            diff=f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n@@\n+changed\n",
        )

        result = run_reviewer(task)

        assert result.status == REVIEW_STATUS_CHANGES_REQUESTED
        assert any(path in fix for fix in result.required_fixes)


def test_reviewer_detects_secret_token_key_filenames():
    assert is_sensitive_path("docs/token-notes.md") is True
    assert is_sensitive_path("config/private_key.txt") is True
    assert is_sensitive_path("app/secret_config.py") is True
    assert is_sensitive_path("README.md") is False


def test_reviewer_changes_requested_if_git_action_artifact_exists(tmp_path):
    workspace = tmp_path / "TASK-0007"
    task = make_task(workspace)
    write_success_artifacts(workspace)
    (workspace / "commit_exit_code.txt").write_text("0\n", encoding="utf-8")

    result = run_reviewer(task)

    assert result.status == REVIEW_STATUS_CHANGES_REQUESTED
    assert "codex_run must not commit, push, create PRs, or deploy before approval." in result.required_fixes


def test_review_report_message_creates_missing_report(tmp_path):
    workspace = tmp_path / "TASK-0007"
    task = make_task(workspace)
    write_success_artifacts(workspace)

    message = build_review_report_message(task)

    assert "Review report: TASK-0007" in message
    assert (workspace / "review_report.md").exists()
