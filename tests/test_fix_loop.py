from pathlib import Path

from app.fix_loop import FIX_PROMPT_FILENAME, REVIEW_COMMENTS_FILENAME, prepare_fix_prompt
from app.task_store import TaskRecord


def make_task(workspace: Path, task_id: str = "TASK-0019") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )


def write_fix_loop_workspace(workspace: Path, branch_name: str = "agent/TASK-0019-fix-loop") -> None:
    workspace.mkdir()
    (workspace / "input.md").write_text("В pdlc-bot добавь Fix Loop\n", encoding="utf-8")
    (workspace / "branch_name.txt").write_text(f"{branch_name}\n", encoding="utf-8")


def test_prepare_fix_prompt_creates_review_comments_and_fix_prompt(tmp_path):
    workspace = tmp_path / "TASK-0019"
    write_fix_loop_workspace(workspace)

    result = prepare_fix_prompt(make_task(workspace), "Кнопка слишком длинная, сократи текст.")

    assert result.ok is True
    assert result.message.startswith("Fix prompt prepared.")
    assert (workspace / REVIEW_COMMENTS_FILENAME).read_text(encoding="utf-8") == "Кнопка слишком длинная, сократи текст.\n"
    fix_prompt = (workspace / FIX_PROMPT_FILENAME).read_text(encoding="utf-8")
    assert "TASK-0019" in fix_prompt
    assert "В pdlc-bot добавь Fix Loop" in fix_prompt
    assert "Кнопка слишком длинная, сократи текст." in fix_prompt
    assert "Continue on existing agent branch" in fix_prompt
    assert "agent/TASK-0019-fix-loop" in fix_prompt
    assert "Do not commit, push, or deploy." in fix_prompt


def test_prepare_fix_prompt_requires_safe_agent_branch(tmp_path):
    workspace = tmp_path / "TASK-0019"
    write_fix_loop_workspace(workspace, branch_name="main")

    result = prepare_fix_prompt(make_task(workspace), "Исправь замечание")

    assert result.ok is False
    assert "branch_name.txt" in result.message
    assert not (workspace / REVIEW_COMMENTS_FILENAME).exists()
    assert not (workspace / FIX_PROMPT_FILENAME).exists()


def test_prepare_fix_prompt_rejects_empty_comments(tmp_path):
    workspace = tmp_path / "TASK-0019"
    write_fix_loop_workspace(workspace)

    result = prepare_fix_prompt(make_task(workspace), "   ")

    assert result.ok is False
    assert "Использование: /fix TASK-0001 <замечания>" in result.message
