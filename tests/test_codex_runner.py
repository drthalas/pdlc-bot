import shlex
from pathlib import Path

from app.codex_runner import (
    GitCommandResult,
    build_branch_name,
    build_codex_branch_prepare_message,
    build_codex_branch_create_message,
    build_codex_git_check_message,
    build_codex_prepare_command,
    build_codex_prepare_message,
    build_codex_run_message,
    build_codex_dry_run_command,
    build_codex_runner_disabled_message,
    get_codex_bin_path,
    get_codex_runner_mode,
    is_git_status_clean,
    is_codex_runner_enabled,
    read_git_status_porcelain,
    write_codex_branch_prepare_artifacts,
    write_codex_branch_create_artifacts,
    write_codex_git_check_artifacts,
    write_codex_run_artifacts,
    write_codex_prepare_artifacts,
)
from app.task_store import TaskRecord


def make_task(workspace: Path, task_id: str = "TASK-0007") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )


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


def test_codex_dry_run_command_is_only_text(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    task = make_task(workspace)

    prompt_path = workspace.resolve() / "codex_prompt.md"
    assert build_codex_dry_run_command(task) == f"cd . && /custom/codex < {shlex.quote(str(prompt_path))}"


def test_codex_runner_prepare_mode_is_recognized(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_RUNNER_MODE", "prepare")

    assert get_codex_runner_mode() == "prepare"


def test_codex_runner_branch_prepare_mode_is_recognized(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_RUNNER_MODE", "branch_prepare")

    assert get_codex_runner_mode() == "branch_prepare"


def test_codex_runner_git_check_mode_is_recognized(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_RUNNER_MODE", "git_check")

    assert get_codex_runner_mode() == "git_check"


def test_codex_runner_branch_create_mode_is_recognized(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_RUNNER_MODE", "branch_create")

    assert get_codex_runner_mode() == "branch_create"


def test_codex_runner_codex_run_mode_is_recognized(monkeypatch):
    monkeypatch.setenv("PDLC_CODEX_RUNNER_MODE", "codex_run")

    assert get_codex_runner_mode() == "codex_run"


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


def test_codex_git_check_clean_status_creates_artifacts(monkeypatch, tmp_path):
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

    result = write_codex_git_check_artifacts(task, git_status_reader=lambda local_path: "")

    assert result.is_clean is True
    assert result.git_status_path == workspace / "git_status_before.txt"
    assert result.git_status_path.read_text(encoding="utf-8") == ""
    assert result.branch_name == "agent/TASK-0007-add-persistent-menu"
    assert result.branch_name_path == workspace / "branch_name.txt"
    assert result.command_path == workspace / "run_codex_command.txt"
    assert result.script_path == workspace / "run_codex.sh"
    assert result.script_path.stat().st_mode & 0o111

    message = build_codex_git_check_message(task, result)
    assert "Codex Runner git_check mode. Working tree is clean." in message
    assert "No branch was created" in message
    assert "No command was executed" in message


def test_codex_git_check_dirty_status_stops_flow(tmp_path):
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

    result = write_codex_git_check_artifacts(task, git_status_reader=lambda local_path: " M app/main.py\n")

    assert result.is_clean is False
    assert result.git_status_path.read_text(encoding="utf-8") == " M app/main.py\n"
    assert result.branch_name is None
    assert not (workspace / "branch_name.txt").exists()
    assert not (workspace / "run_codex_command.txt").exists()
    assert not (workspace / "run_codex.sh").exists()

    message = build_codex_git_check_message(task, result)
    assert "Working tree is dirty" in message
    assert "No branch was created" in message
    assert "No command was executed" in message


def test_codex_git_check_error_is_safe(tmp_path):
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )

    def failing_reader(local_path: str) -> str:
        raise RuntimeError("git status timed out after 10 seconds")

    try:
        write_codex_git_check_artifacts(task, git_status_reader=failing_reader)
    except RuntimeError as error:
        assert "timed out" in str(error)
    else:
        raise AssertionError("Expected RuntimeError")


def test_read_git_status_uses_only_read_only_git_status(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = ""
        stderr = ""

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr("app.codex_runner.subprocess.run", fake_run)

    assert read_git_status_porcelain("/tmp/project", timeout=3) == ""
    assert calls == [
        (
            ["git", "status", "--porcelain"],
            {
                "cwd": "/tmp/project",
                "capture_output": True,
                "text": True,
                "timeout": 3,
                "check": False,
            },
        )
    ]


def test_codex_branch_create_clean_flow_creates_artifacts(monkeypatch, tmp_path):
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
    status_calls = []
    branch_calls = []

    def fake_status(local_path: str) -> str:
        status_calls.append(local_path)
        return ""

    def fake_branch(local_path: str, branch_name: str) -> GitCommandResult:
        branch_calls.append((local_path, branch_name))
        return GitCommandResult(stdout="", stderr="", exit_code=0)

    result = write_codex_branch_create_artifacts(task, git_status_reader=fake_status, branch_creator=fake_branch)

    assert status_calls == ["/tmp/project", "/tmp/project"]
    assert branch_calls == [("/tmp/project", "agent/TASK-0007-add-persistent-menu")]
    assert result.is_clean is True
    assert result.branch_created is True
    assert result.branch_name == "agent/TASK-0007-add-persistent-menu"
    assert result.git_status_before_path == workspace / "git_status_before.txt"
    assert result.branch_name_path == workspace / "branch_name.txt"
    assert result.branch_stdout_path == workspace / "branch_create_stdout.txt"
    assert result.branch_stderr_path == workspace / "branch_create_stderr.txt"
    assert result.branch_exit_code_path == workspace / "branch_create_exit_code.txt"
    assert result.git_status_after_path == workspace / "git_status_after_branch.txt"
    assert result.command_path == workspace / "run_codex_command.txt"
    assert result.script_path == workspace / "run_codex.sh"
    assert result.branch_exit_code_path.read_text(encoding="utf-8") == "0\n"
    assert result.script_path.stat().st_mode & 0o111

    message = build_codex_branch_create_message(task, result)
    assert "Codex Runner branch_create mode" in message
    assert "Branch created: agent/TASK-0007-add-persistent-menu" in message
    assert "No Codex command was executed" in message
    assert "No commit/push was performed" in message


def test_codex_branch_create_dirty_flow_does_not_create_branch(tmp_path):
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "input.md").write_text("Add persistent menu\n", encoding="utf-8")
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )
    branch_calls = []

    def fake_branch(local_path: str, branch_name: str) -> GitCommandResult:
        branch_calls.append((local_path, branch_name))
        return GitCommandResult(stdout="", stderr="", exit_code=0)

    result = write_codex_branch_create_artifacts(
        task,
        git_status_reader=lambda local_path: " M app/main.py\n",
        branch_creator=fake_branch,
    )

    assert branch_calls == []
    assert result.is_clean is False
    assert result.branch_created is False
    assert result.git_status_before_path.read_text(encoding="utf-8") == " M app/main.py\n"
    assert not (workspace / "branch_name.txt").exists()

    message = build_codex_branch_create_message(task, result)
    assert "Working tree is dirty" in message
    assert "No branch was created" in message


def test_codex_branch_create_existing_branch_error_stops_safely(tmp_path):
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "input.md").write_text("Add persistent menu\n", encoding="utf-8")
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = TaskRecord(
        task_id="TASK-0007",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )

    def existing_branch(local_path: str, branch_name: str) -> GitCommandResult:
        return GitCommandResult(
            stdout="",
            stderr=f"fatal: a branch named '{branch_name}' already exists\n",
            exit_code=128,
        )

    result = write_codex_branch_create_artifacts(
        task,
        git_status_reader=lambda local_path: "",
        branch_creator=existing_branch,
    )

    assert result.is_clean is True
    assert result.branch_created is False
    assert result.branch_exit_code_path.read_text(encoding="utf-8") == "128\n"
    assert "already exists" in result.branch_stderr_path.read_text(encoding="utf-8")
    assert not (workspace / "git_status_after_branch.txt").exists()
    assert not (workspace / "run_codex_command.txt").exists()
    assert not (workspace / "run_codex.sh").exists()

    message = build_codex_branch_create_message(task, result)
    assert "Branch was not created" in message
    assert "already exists" in message
    assert "No Codex command was executed" in message


def test_create_git_branch_uses_only_checkout_new_branch(monkeypatch):
    calls = []

    class Result:
        returncode = 0
        stdout = "created\n"
        stderr = ""

    def fake_run(command, **kwargs):
        calls.append((command, kwargs))
        return Result()

    monkeypatch.setattr("app.codex_runner.subprocess.run", fake_run)

    from app.codex_runner import create_git_branch

    result = create_git_branch("/tmp/project", "agent/TASK-0007-task", timeout=3)

    assert result == GitCommandResult(stdout="created\n", stderr="", exit_code=0)
    assert calls == [
        (
            ["git", "checkout", "-b", "agent/TASK-0007-task"],
            {
                "cwd": "/tmp/project",
                "capture_output": True,
                "text": True,
                "timeout": 3,
                "check": False,
            },
        )
    ]


def test_codex_run_clean_flow_creates_branch_invokes_codex_and_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    monkeypatch.setenv("PDLC_CODEX_TIMEOUT_SECONDS", "123")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "input.md").write_text("Add persistent menu\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("Do the task.\n", encoding="utf-8")
    (workspace / "project.json").write_text(
        '{"local_path": "/tmp/project", "test_commands": ["pytest -q", "python -m app.main"]}\n',
        encoding="utf-8",
    )
    task = make_task(workspace)
    status_calls = []
    branch_calls = []
    command_calls = []

    def fake_status(local_path: str) -> str:
        status_calls.append(local_path)
        return " M app/main.py\n" if len(status_calls) == 2 else ""

    def fake_branch(local_path: str, branch_name: str) -> GitCommandResult:
        branch_calls.append((local_path, branch_name))
        return GitCommandResult(stdout="created\n", stderr="", exit_code=0)

    def fake_command(command, local_path, timeout, stdin_path):
        command_calls.append((command, local_path, timeout, stdin_path))
        if command == ["/custom/codex"]:
            return GitCommandResult(stdout="codex ok\n", stderr="", exit_code=0)
        if command == ["git", "diff"]:
            return GitCommandResult(stdout="diff --git a/app/main.py b/app/main.py\n", stderr="", exit_code=0)
        if command == ["git", "diff", "--stat"]:
            return GitCommandResult(stdout=" app/main.py | 1 +\n", stderr="", exit_code=0)
        return GitCommandResult(stdout="tests ok\n", stderr="", exit_code=0)

    result = write_codex_run_artifacts(
        task,
        git_status_reader=fake_status,
        branch_creator=fake_branch,
        command_runner=fake_command,
    )

    assert status_calls == ["/tmp/project", "/tmp/project"]
    assert branch_calls == [("/tmp/project", "agent/TASK-0007-add-persistent-menu")]
    assert command_calls[0] == (["/custom/codex"], "/tmp/project", 123, workspace / "codex_prompt.md")
    assert ["git", "diff"] in [call[0] for call in command_calls]
    assert ["git", "diff", "--stat"] in [call[0] for call in command_calls]
    assert ["pytest", "-q"] in [call[0] for call in command_calls]
    assert ["python", "-m", "app.main"] in [call[0] for call in command_calls]
    assert result.codex_ran is True
    assert result.codex_exit_code == 0
    assert result.tests_passed is True
    assert result.branch_name == "agent/TASK-0007-add-persistent-menu"
    assert result.codex_stdout_path.read_text(encoding="utf-8") == "codex ok\n"
    assert result.codex_exit_code_path.read_text(encoding="utf-8") == "0\n"
    assert result.diff_path.read_text(encoding="utf-8").startswith("diff --git")
    assert "pytest -q" in result.test_report_path.read_text(encoding="utf-8")
    assert "No commit, push, PR, or deploy was performed." in result.developer_report_path.read_text(encoding="utf-8")

    message = build_codex_run_message(task, result)
    assert "Codex finished" in message
    assert "Branch: agent/TASK-0007-add-persistent-menu" in message
    assert "Tests: passed" in message
    assert "No commit/push/deploy was performed" in message


def test_codex_run_dirty_flow_stops_before_branch_or_codex(tmp_path):
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = make_task(workspace)
    branch_calls = []
    command_calls = []

    result = write_codex_run_artifacts(
        task,
        git_status_reader=lambda local_path: " M app/main.py\n",
        branch_creator=lambda local_path, branch_name: branch_calls.append((local_path, branch_name)),
        command_runner=lambda command, local_path, timeout, stdin_path: command_calls.append(command),
    )

    assert result.is_clean is False
    assert result.branch_created is False
    assert result.codex_ran is False
    assert branch_calls == []
    assert command_calls == []
    assert result.git_status_before_path.read_text(encoding="utf-8") == " M app/main.py\n"


def test_codex_run_non_zero_exit_saves_logs_and_report(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "input.md").write_text("Add persistent menu\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("Do the task.\n", encoding="utf-8")
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = make_task(workspace)

    def fake_command(command, local_path, timeout, stdin_path):
        if command == ["/custom/codex"]:
            return GitCommandResult(stdout="", stderr="codex failed\n", exit_code=2)
        if command == ["git", "diff"]:
            return GitCommandResult(stdout="", stderr="", exit_code=0)
        if command == ["git", "diff", "--stat"]:
            return GitCommandResult(stdout="", stderr="", exit_code=0)
        return GitCommandResult(stdout="tests ok\n", stderr="", exit_code=0)

    result = write_codex_run_artifacts(
        task,
        git_status_reader=lambda local_path: "",
        branch_creator=lambda local_path, branch_name: GitCommandResult(stdout="", stderr="", exit_code=0),
        command_runner=fake_command,
    )

    assert result.codex_exit_code == 2
    assert result.codex_stderr_path.read_text(encoding="utf-8") == "codex failed\n"
    assert "Codex exited non-zero" in result.developer_report_path.read_text(encoding="utf-8")
    assert "Codex failed" in build_codex_run_message(task, result)


def test_codex_run_does_not_call_commit_push_or_deploy(monkeypatch, tmp_path):
    monkeypatch.setenv("PDLC_CODEX_BIN", "/custom/codex")
    workspace = tmp_path / "TASK-0007"
    workspace.mkdir()
    (workspace / "input.md").write_text("Add persistent menu\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("Do the task.\n", encoding="utf-8")
    (workspace / "project.json").write_text('{"local_path": "/tmp/project"}\n', encoding="utf-8")
    task = make_task(workspace)
    commands = []

    def fake_command(command, local_path, timeout, stdin_path):
        commands.append(command)
        if command in (["git", "diff"], ["git", "diff", "--stat"]):
            return GitCommandResult(stdout="", stderr="", exit_code=0)
        return GitCommandResult(stdout="", stderr="", exit_code=0)

    write_codex_run_artifacts(
        task,
        git_status_reader=lambda local_path: "",
        branch_creator=lambda local_path, branch_name: GitCommandResult(stdout="", stderr="", exit_code=0),
        command_runner=fake_command,
    )

    forbidden = [
        ["git", "commit"],
        ["git", "push"],
        ["gh", "pr"],
        ["railway"],
    ]
    for command in commands:
        assert command[:2] not in forbidden
        assert command[:1] not in forbidden
