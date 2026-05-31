from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re

from app.post_run_controls import (
    TASK_RESULT_COMMITTED,
    TASK_RESULT_READY_FOR_POST_RUN_ACTIONS,
    TASK_RESULT_RUNNING,
    task_result_state,
)
from app.task_store import TaskRecord, TaskStore


PROMPT_PREVIEW_LIMIT = 3500
TASK_TITLE_LIMIT = 72

STATUS_LABELS = {
    "created": "создана",
    "analyzed": "проанализирована",
    "planned": "план готов",
    "prompt_ready": "prompt готов",
    "codex_running": "Codex выполняется",
    "coding": "в разработке",
    "testing": "тестирование",
    "committed": "закоммичена",
    "failed": "ошибка",
    "cancelled": "отменена",
}


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


def _has_artifact(record: TaskRecord, artifact_name: str) -> bool:
    return (Path(record.workspace_path) / artifact_name).is_file()


def _artifact_text(record: TaskRecord, artifact_name: str) -> str:
    path = Path(record.workspace_path) / artifact_name
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _tests_passed(record: TaskRecord) -> bool:
    report = _artifact_text(record, "test_report.md")
    exit_codes = re.findall(r"^Exit code: (\d+)$", report, flags=re.MULTILINE)
    return bool(exit_codes) and all(code == "0" for code in exit_codes)


def _codex_done(record: TaskRecord) -> bool:
    return _artifact_text(record, "codex_exit_code.txt").strip() == "0"


def _task_stage(record: TaskRecord) -> str:
    state = task_result_state(record)
    if state == TASK_RESULT_COMMITTED:
        return "Готово к push после локального commit"
    if state == TASK_RESULT_READY_FOR_POST_RUN_ACTIONS:
        return "Codex завершён, можно проверить diff и решить по commit"
    if state == TASK_RESULT_RUNNING:
        return "Codex выполняется"
    if record.status == "failed":
        return "Требуется разбор ошибки"
    if _has_artifact(record, "codex_prompt.md"):
        return "Prompt готов, можно запускать Codex"
    return "Задача создана, идёт подготовка prompt"


def _progress_line(done: bool, label: str, detail: str | None = None) -> str:
    marker = "✅" if done else "⬜"
    suffix = f" — {detail}" if detail else ""
    return f"{marker} {label}{suffix}"


def _progress_lines(record: TaskRecord) -> list[str]:
    review_done = _has_artifact(record, "review_report.md")
    return [
        _progress_line(True, "задача создана"),
        _progress_line(_has_artifact(record, "codex_prompt.md"), "prompt готов"),
        _progress_line(_codex_done(record), "Codex выполнен"),
        _progress_line(_tests_passed(record), "тесты пройдены"),
        _progress_line(review_done, "review выполнен" if review_done else "review ожидается"),
        _progress_line(record.status == "committed", "commit сделан"),
    ]


def _status_label(status: str) -> str:
    return STATUS_LABELS.get(status, status)


def format_task_created_response(
    record: TaskRecord,
    project_detected: bool,
    artifacts: list[str],
) -> str:
    if not project_detected:
        return (
            f"⚠️ Задача создана: {record.task_id}\n\n"
            "Проект: не определён\n"
            f"Статус: {_status_label(record.status)}\n\n"
            "В следующий раз укажи название проекта или alias из /projects."
        )

    return format_task_details_response(record, artifacts=artifacts, header=f"✅ Задача создана: {record.task_id}")


def format_task_details_response(record: TaskRecord, artifacts: list[str], header: str | None = None) -> str:
    project_name = record.project_name or "не определён"
    lines = [
        header or f"📄 Задача {record.task_id}",
        "",
        f"Название: {task_title(record)}",
        f"Проект: {project_name}",
        f"Статус: {_status_label(record.status)}",
        f"Текущий этап: {_task_stage(record)}",
        "",
        "Прогресс:",
        *_progress_lines(record),
        "",
        "Доступные действия — в кнопках ниже.",
    ]

    if artifacts:
        lines.extend(["Технические файлы скрыты в отдельной кнопке."])

    return "\n".join(lines)


def format_task_artifacts_response(record: TaskRecord, artifacts: list[str]) -> str:
    if artifacts:
        artifact_lines = "\n".join(f"- {artifact}" for artifact in artifacts)
    else:
        artifact_lines = "Технические файлы не найдены."
    return f"🛠 Технические детали {record.task_id}\n\nРабочая папка: {record.workspace_path}\n\nФайлы:\n{artifact_lines}"


def build_prompt_response(
    store: TaskStore,
    task_id: str,
    preview_limit: int = PROMPT_PREVIEW_LIMIT,
) -> PromptResponse:
    record = store.get_task(task_id)
    if record is None:
        return PromptResponse(message=f"Задача {task_id} не найдена.", found=False)

    prompt_path = Path(record.workspace_path) / "codex_prompt.md"
    if not prompt_path.exists() or not prompt_path.is_file():
        return PromptResponse(message=f"Codex prompt для {task_id} не найден.", found=False)

    prompt = prompt_path.read_text(encoding="utf-8")
    if len(prompt) <= preview_limit:
        return PromptResponse(message=prompt, found=True)

    preview = prompt[:preview_limit].rstrip()
    message = (
        f"{preview}\n\n"
        f"[Prompt обрезан. Полная версия доступна в {prompt_path}.]"
    )
    return PromptResponse(message=message, found=True)
