import subprocess
from pathlib import Path

from app.post_run_controls import (
    build_commit_message,
    build_show_diff_message,
    changed_files_for_commit,
    commit_task_changes,
    discard_task_changes,
    is_git_push_enabled,
    is_safe_agent_branch,
    push_task_branch,
    should_show_post_run_controls,
)
from app.task_store import TaskRecord


def make_task(workspace: Path, task_id: str = "TASK-0013") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )


def write_post_run_artifacts(workspace: Path, branch_name: str = "agent/TASK-0013-post-run-controls") -> None:
    workspace.mkdir()
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    (workspace / "input.md").write_text("Add post-run controls for Codex Runner\n", encoding="utf-8")
    (workspace / "branch_name.txt").write_text(f"{branch_name}\n", encoding="utf-8")
    (workspace / "codex_exit_code.txt").write_text("0\n", encoding="utf-8")
    (workspace / "diff.patch").write_text("diff --git a/app.py b/app.py\n+change\n", encoding="utf-8")
    (workspace / "test_report.md").write_text("Exit code: 0\n\nExit code: 0\n", encoding="utf-8")


def completed(command, stdout="", stderr="", returncode=0):
    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)


def test_should_show_post_run_controls_requires_success_diff_and_tests(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)
    task = make_task(workspace)

    assert should_show_post_run_controls(task) is True

    (workspace / "test_report.md").write_text("Exit code: 1\n", encoding="utf-8")
    assert should_show_post_run_controls(task) is False


def test_show_diff_reads_diff_patch(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)

    message = build_show_diff_message(make_task(workspace))

    assert "Diff for TASK-0013" in message
    assert "diff --git a/app.py b/app.py" in message


def test_show_diff_falls_back_to_diff_stat_artifact(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)
    (workspace / "diff.patch").write_text("", encoding="utf-8")
    (workspace / "developer_report.md").write_text(
        "# Developer Report\n\n## Diff Stat\n\n```text\n app.py | 1 +\n```\n",
        encoding="utf-8",
    )

    message = build_show_diff_message(make_task(workspace))

    assert "Diff stat" in message
    assert "app.py | 1 +" in message


def test_commit_message_uses_task_id_and_short_title(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)

    assert build_commit_message(make_task(workspace)) == "TASK-0013: Add post-run controls for Codex Runner"


def test_safe_agent_branch_validation():
    assert is_safe_agent_branch("agent/TASK-0013-post-run-controls") is True
    assert is_safe_agent_branch("agent/TASK-0013") is True
    assert is_safe_agent_branch("main") is False
    assert is_safe_agent_branch("feature/TASK-0013") is False


def test_commit_task_changes_stages_allowed_files_explicitly_and_does_not_push(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)
    calls = []

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        if command == ["git", "branch", "--show-current"]:
            return completed(command, stdout="agent/TASK-0013-post-run-controls\n")
        if command == ["git", "status", "--porcelain"]:
            return completed(command, stdout=" M app/telegram_bot.py\n?? app/post_run_controls.py\n")
        return completed(command, stdout="")

    result = commit_task_changes(make_task(workspace), runner=fake_run)

    assert result.ok is True
    assert calls[0][0] == ["git", "branch", "--show-current"]
    assert calls[1][0] == ["git", "status", "--porcelain"]
    assert calls[2][0] == ["git", "add", "app/telegram_bot.py", "app/post_run_controls.py"]
    assert calls[3][0] == ["git", "commit", "-m", "TASK-0013: Add post-run controls for Codex Runner"]
    assert all(call[1]["cwd"] == "/tmp/project" for call in calls)
    assert ["git", "add", "-A"] not in [call[0] for call in calls]
    assert ["git", "push"] not in [call[0][:2] for call in calls]


def test_commit_refuses_non_agent_branch(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        return completed(command, stdout="main\n")

    result = commit_task_changes(make_task(workspace), runner=fake_run)

    assert result.ok is False
    assert "Refusing git action outside agent/TASK-* branch" in result.message
    assert calls == [["git", "branch", "--show-current"]]


def test_changed_files_for_commit_blocks_denied_paths():
    def fake_run(command, **kwargs):
        return completed(
            command,
            stdout=(
                " M app/main.py\n"
                "?? .env\n"
                "?? tasks/TASK-0001/input.md\n"
                "?? config/projects.yaml\n"
                "?? local-token.txt\n"
                "?? data.sqlite3\n"
            ),
        )

    files, error = changed_files_for_commit("/tmp/project", fake_run)

    assert files == []
    assert error is not None
    assert "protected files" in error.message
    assert ".env" in error.message
    assert "tasks/TASK-0001/input.md" in error.message
    assert "config/projects.yaml" in error.message
    assert "local-token.txt" in error.message
    assert "data.sqlite3" in error.message


def test_changed_files_for_commit_allows_docs_with_key_word():
    def fake_run(command, **kwargs):
        return completed(command, stdout=" M README.md\n M docs/CODEX_RUNNER_V0.md\n M tests/test_post_run_controls.py\n")

    files, error = changed_files_for_commit("/tmp/project", fake_run)

    assert error is None
    assert files == ["README.md", "docs/CODEX_RUNNER_V0.md", "tests/test_post_run_controls.py"]


def test_push_disabled_by_default(monkeypatch, tmp_path):
    monkeypatch.delenv("PDLC_ENABLE_GIT_PUSH", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)
    calls = []

    result = push_task_branch(make_task(workspace), runner=lambda command, **kwargs: calls.append(command))

    assert is_git_push_enabled() is False
    assert result.ok is False
    assert result.message == "Push is disabled by configuration."
    assert calls == []


def test_push_task_branch_requires_confirm_path_env_flag_and_uses_origin_branch(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_ENABLE_GIT_PUSH", "true")
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["git", "branch", "--show-current"]:
            return completed(command, stdout="agent/TASK-0013-post-run-controls\n")
        return completed(command)

    result = push_task_branch(make_task(workspace), runner=fake_run)

    assert result.ok is True
    assert calls == [
        ["git", "branch", "--show-current"],
        ["git", "push", "-u", "origin", "agent/TASK-0013-post-run-controls"],
    ]


def test_discard_task_changes_resets_then_checks_out_main(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_post_run_artifacts(workspace)
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        if command == ["git", "branch", "--show-current"]:
            return completed(command, stdout="agent/TASK-0013-post-run-controls\n")
        return completed(command)

    result = discard_task_changes(make_task(workspace), runner=fake_run)

    assert result.ok is True
    assert calls == [
        ["git", "branch", "--show-current"],
        ["git", "reset", "--hard"],
        ["git", "checkout", "main"],
    ]
