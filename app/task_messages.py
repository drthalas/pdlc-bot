from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.task_store import TaskRecord, TaskStore


PROMPT_PREVIEW_LIMIT = 3500
TASK_TITLE_LIMIT = 72


@dataclass(frozen=True)
class PromptResponse:
    message: str
    found: bool


def _strip_task_prefix(title: str, project_name: str | None) -> str:
    cleaned = " ".join(title.strip().split())
    if project_name:
        escaped_project = re.escape(project_name)
        cleaned = re.sub(rf"^(?:в|для)\s+{escaped_project}\s+", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(rf"^{escaped_project}\s*[:—-]?\s*", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip(" :—-") or title.strip()


def _truncate_title(title: str, limit: int = TASK_TITLE_LIMIT) -> str:
    if len(title) <= limit:
        return title
    return f"{title[: limit - 1].rstrip()}…"


def task_title(record: TaskRecord, limit: int = TASK_TITLE_LIMIT) -> str:
    input_path = Path(record.workspace_path) / "input.md"
    try:
        lines = input_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return record.task_id

    for line in lines:
        normalized = " ".join(line.strip().split())
        if normalized:
            return _truncate_title(_strip_task_prefix(normalized, record.project_name), limit=limit)
    return record.task_id


def format_task_created_response(
    record: TaskRecord,
    project_detected: bool,
    artifacts: list[str],
) -> str:
    if not project_detected:
        return (
            f"⚠️ Task created: {record.task_id}\n\n"
            "Project: not detected\n"
            f"Status: {record.status}\n"
            f"Workspace: {record.workspace_path}\n\n"
            "Please mention a project name or alias from /projects next time."
        )

    project_name = record.project_name or "not detected"
    lines = [
        f"✅ Task created: {record.task_id}",
        "",
        f"Project: {project_name}",
        f"Status: {record.status}",
        f"Workspace: {record.workspace_path}",
    ]
    if artifacts:
        lines.extend(["", "Artifacts:"])
        lines.extend(f"- {artifact}" for artifact in artifacts)

    lines.extend(
        [
            "",
            "Next:",
            f"- /task {record.task_id} — show task details",
            f"- /prompt {record.task_id} — show Codex prompt",
        ]
    )
    return "\n".join(lines)


def format_task_details_response(record: TaskRecord, artifacts: list[str]) -> str:
    project_name = record.project_name or "not detected"
    lines = [
        record.task_id,
        "",
        f"Title: {task_title(record)}",
        f"Project: {project_name}",
        f"Status: {record.status}",
        f"Workspace: {record.workspace_path}",
    ]

    if artifacts:
        lines.extend(["", "Artifacts:"])
        lines.extend(f"- {artifact}" for artifact in artifacts)

    return "\n".join(lines)


def build_prompt_response(
    store: TaskStore,
    task_id: str,
    preview_limit: int = PROMPT_PREVIEW_LIMIT,
) -> PromptResponse:
    record = store.get_task(task_id)
    if record is None:
        return PromptResponse(message=f"Task {task_id} not found.", found=False)

    prompt_path = Path(record.workspace_path) / "codex_prompt.md"
    if not prompt_path.exists() or not prompt_path.is_file():
        return PromptResponse(message=f"Codex prompt not found for {task_id}.", found=False)

    prompt = prompt_path.read_text(encoding="utf-8")
    if len(prompt) <= preview_limit:
        return PromptResponse(message=prompt, found=True)

    preview = prompt[:preview_limit].rstrip()
    message = (
        f"{preview}\n\n"
        f"[Prompt truncated. Full prompt is available at {prompt_path}.]"
    )
    return PromptResponse(message=message, found=True)
