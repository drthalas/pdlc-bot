from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from app.post_run_controls import is_safe_agent_branch
from app.task_store import TaskRecord


REVIEW_COMMENTS_FILENAME = "review_comments.md"
FIX_PROMPT_FILENAME = "fix_prompt.md"


@dataclass(frozen=True)
class FixPromptResult:
    ok: bool
    message: str
    review_comments_path: Path | None = None
    fix_prompt_path: Path | None = None
    branch_name: str | None = None


def _workspace(task: TaskRecord) -> Path:
    return Path(task.workspace_path)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _read_branch_name(task: TaskRecord) -> str | None:
    branch_name = _read_text(_workspace(task) / "branch_name.txt").strip()
    return branch_name or None


def build_fix_prompt(task: TaskRecord, review_comments: str, branch_name: str) -> str:
    user_request = _read_text(_workspace(task) / "input.md").strip() or "Original user request is unavailable."
    return (
        f"# Fix prompt for {task.task_id}\n\n"
        "You are Codex continuing an existing PDLC task.\n\n"
        f"Task: {task.task_id}\n"
        f"Project: {task.project_name or 'unknown'}\n"
        f"Current branch: {branch_name}\n\n"
        "## Original user request\n\n"
        f"{user_request}\n\n"
        "## Review comments\n\n"
        f"{review_comments.strip()}\n\n"
        "## Instructions\n\n"
        "- Continue on existing agent branch.\n"
        f"- Use the current branch: `{branch_name}`.\n"
        "- Do not start the task from scratch.\n"
        "- Keep scope limited to the review comments.\n"
        "- Do not change unrelated files.\n"
        "- Do not modify `.env`, secrets, local runtime config, `tasks/`, or SQLite files.\n"
        "- Do not commit, push, or deploy.\n"
        "- After the fix, run the project tests and save the result in `test_report.md`.\n"
        "- Update `developer_report.md` with what changed, verification result, and remaining risk.\n"
    )


def prepare_fix_prompt(task: TaskRecord, review_comments: str) -> FixPromptResult:
    comments = review_comments.strip()
    if not comments:
        return FixPromptResult(False, "Замечания пустые. Использование: /fix TASK-0001 <замечания>")

    branch_name = _read_branch_name(task)
    if not is_safe_agent_branch(branch_name):
        return FixPromptResult(
            False,
            f"Fix loop недоступен для {task.task_id}: branch_name.txt отсутствует или не является agent/TASK-* branch.",
            branch_name=branch_name,
        )

    workspace = _workspace(task)
    workspace.mkdir(parents=True, exist_ok=True)
    review_comments_path = workspace / REVIEW_COMMENTS_FILENAME
    fix_prompt_path = workspace / FIX_PROMPT_FILENAME

    review_comments_path.write_text(f"{comments}\n", encoding="utf-8")
    fix_prompt_path.write_text(build_fix_prompt(task, comments, branch_name), encoding="utf-8")

    return FixPromptResult(
        True,
        (
            "Fix prompt prepared.\n\n"
            f"Task: {task.task_id}\n"
            f"Branch: {branch_name}\n"
            "Artifacts:\n"
            f"- {REVIEW_COMMENTS_FILENAME}\n"
            f"- {FIX_PROMPT_FILENAME}"
        ),
        review_comments_path=review_comments_path,
        fix_prompt_path=fix_prompt_path,
        branch_name=branch_name,
    )
