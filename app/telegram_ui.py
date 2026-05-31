from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.post_run_controls import (
    TASK_RESULT_COMMITTED,
    TASK_RESULT_READY_FOR_POST_RUN_ACTIONS,
    TASK_RESULT_RUNNING,
    task_result_state,
)
from app.project_registry import Project
from app.task_store import TaskRecord
from app.task_messages import task_title


MENU_BUTTON = "🏠 Меню"
PROJECTS_BUTTON = "📋 Проекты"
TASKS_BUTTON = "🗂 Задачи"
STATUS_BUTTON = "ℹ️ Статус"
RUNBOOK_BUTTON = "📘 Runbook"
LEGACY_MENU_BUTTON = "🏠 Menu"
LEGACY_PROJECTS_BUTTON = "📋 Projects"
LEGACY_TASKS_BUTTON = "🗂 Tasks"
LEGACY_STATUS_BUTTON = "ℹ️ Status"
RECENT_TASKS_LIMIT = 10

MENU_ACTIONS = {
    MENU_BUTTON: "menu",
    LEGACY_MENU_BUTTON: "menu",
    PROJECTS_BUTTON: "projects",
    LEGACY_PROJECTS_BUTTON: "projects",
    TASKS_BUTTON: "tasks",
    LEGACY_TASKS_BUTTON: "tasks",
    STATUS_BUTTON: "status",
    LEGACY_STATUS_BUTTON: "status",
    RUNBOOK_BUTTON: "runbook",
}


def get_menu_action(text: str) -> str | None:
    return MENU_ACTIONS.get(text.strip())


def build_persistent_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [
            [MENU_BUTTON, PROJECTS_BUTTON],
            [TASKS_BUTTON, STATUS_BUTTON],
        ],
        resize_keyboard=True,
        is_persistent=True,
        input_field_placeholder="Отправь задачу или выбери действие",
    )


def build_start_message() -> str:
    return (
        "PDLC Bot работает.\n\n"
        "Здесь можно создавать задачи разработки и готовить prompt для Codex.\n\n"
        "Выбери действие:"
    )


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Проекты", callback_data="projects:show"),
                InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent"),
            ],
            [
                InlineKeyboardButton("ℹ️ Статус", callback_data="status:show"),
                InlineKeyboardButton("📘 Runbook", callback_data="runbook:show"),
            ],
        ]
    )


def build_runbook_message() -> str:
    return (
        "Runbook для Mac mini: `docs/MAC_MINI_RUNBOOK.md`\n\n"
        "Используй runbook для операционных задач:\n"
        "- статус сервиса\n"
        "- логи\n"
        "- restart\n"
        "- проверка deployed version\n\n"
        "Из соображений безопасности Telegram-сводка не содержит длинные shell-команды, токены или секретные детали."
    )


def build_prompt_ready_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("▶️ Запустить Codex", callback_data=f"task:run_codex:{task_id}")],
            [
                InlineKeyboardButton("📄 Детали задачи", callback_data=f"task:details:{task_id}"),
                InlineKeyboardButton("🧠 Codex prompt", callback_data=f"task:prompt:{task_id}"),
            ],
            [InlineKeyboardButton("🛠 Технические детали", callback_data=f"task:artifacts:{task_id}")],
            [InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent")],
        ]
    )


def build_task_actions_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return build_prompt_ready_task_keyboard(task_id)


def build_task_details_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("▶️ Запустить Codex", callback_data=f"task:run_codex:{task_id}")],
            [InlineKeyboardButton("🧠 Codex prompt", callback_data=f"task:prompt:{task_id}")],
            [InlineKeyboardButton("🛠 Технические детали", callback_data=f"task:artifacts:{task_id}")],
            [InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent")],
        ]
    )


def build_codex_post_run_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Показать diff", callback_data=f"task:show_diff:{task_id}"),
                InlineKeyboardButton("🧪 Запустить тесты ещё раз", callback_data=f"task:tests_again:{task_id}"),
            ],
            [
                InlineKeyboardButton("✅ Закоммитить изменения", callback_data=f"task:commit:{task_id}"),
                InlineKeyboardButton("🧹 Откатить изменения", callback_data=f"task:discard:{task_id}"),
            ],
            [InlineKeyboardButton("🛠 Технические детали", callback_data=f"task:artifacts:{task_id}")],
            [InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent")],
        ]
    )


def build_committed_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📤 Отправить branch", callback_data=f"task:push:{task_id}")],
            [InlineKeyboardButton("🛠 Технические детали", callback_data=f"task:artifacts:{task_id}")],
            [InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent")],
        ]
    )


def build_running_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏳ Выполняется", callback_data=f"task:details:{task_id}")],
            [InlineKeyboardButton("🛠 Технические детали", callback_data=f"task:artifacts:{task_id}")],
            [InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent")],
        ]
    )


def build_task_action_keyboard(task: TaskRecord) -> InlineKeyboardMarkup:
    state = task_result_state(task)
    if state == TASK_RESULT_READY_FOR_POST_RUN_ACTIONS:
        return build_codex_post_run_keyboard(task.task_id)
    if state == TASK_RESULT_COMMITTED:
        return build_committed_task_keyboard(task.task_id)
    if state == TASK_RESULT_RUNNING:
        return build_running_task_keyboard(task.task_id)
    return build_prompt_ready_task_keyboard(task.task_id)


def build_commit_confirm_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("✅ Подтвердить commit", callback_data=f"task:confirm_commit:{task_id}"),
                InlineKeyboardButton("Отмена", callback_data=f"task:details:{task_id}"),
            ]
        ]
    )


def build_push_branch_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📤 Отправить branch", callback_data=f"task:push:{task_id}"),
                InlineKeyboardButton("📄 Детали задачи", callback_data=f"task:details:{task_id}"),
            ]
        ]
    )


def build_push_confirm_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📤 Подтвердить push", callback_data=f"task:confirm_push:{task_id}"),
                InlineKeyboardButton("Отмена", callback_data=f"task:details:{task_id}"),
            ]
        ]
    )


def build_discard_confirm_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🧹 Подтвердить откат", callback_data=f"task:confirm_discard:{task_id}"),
                InlineKeyboardButton("Отмена", callback_data=f"task:details:{task_id}"),
            ]
        ]
    )


def _visible_recent_tasks(tasks: list[TaskRecord]) -> list[TaskRecord]:
    return tasks[:RECENT_TASKS_LIMIT]


def _has_archive(tasks: list[TaskRecord]) -> bool:
    return len(tasks) > RECENT_TASKS_LIMIT


def build_recent_tasks_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "Задачи ещё не созданы."

    lines = ["Последние задачи:", ""]
    for task in _visible_recent_tasks(tasks):
        project_name = task.project_name or "не определён"
        lines.append(f"{task.task_id} — {project_name} — {task_title(task)}")
    if _has_archive(tasks):
        lines.extend(["", "Более старые задачи доступны в архиве."])
    return "\n".join(lines)


def build_recent_tasks_keyboard(tasks: list[TaskRecord], include_archive: bool | None = None) -> InlineKeyboardMarkup | None:
    if not tasks:
        return None
    rows = [
        [InlineKeyboardButton(f"{task.task_id} — {task_title(task, limit=48)}", callback_data=f"task:details:{task.task_id}")]
        for task in _visible_recent_tasks(tasks)
    ]
    if include_archive is None:
        include_archive = _has_archive(tasks)
    if include_archive:
        rows.append([InlineKeyboardButton("📦 Архив задач", callback_data="tasks:archive")])
    return InlineKeyboardMarkup(
        rows
    )


def build_archived_tasks_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "В архиве пока нет задач."

    lines = ["📦 Архив задач:", ""]
    for task in tasks:
        project_name = task.project_name or "не определён"
        lines.append(f"{task.task_id} — {project_name} — {task_title(task)}")
    return "\n".join(lines)


def build_archived_tasks_keyboard(tasks: list[TaskRecord]) -> InlineKeyboardMarkup | None:
    rows = [
        [InlineKeyboardButton(f"{task.task_id} — {task_title(task, limit=48)}", callback_data=f"task:details:{task.task_id}")]
        for task in tasks
    ]
    rows.append([InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent")])
    return InlineKeyboardMarkup(rows)


def build_projects_message(projects: list[Project]) -> str:
    if not projects:
        return "Проекты не настроены. Сначала создай config/projects.yaml."

    lines = ["Настроенные проекты:", ""]
    lines.extend(f"- {project.name}" for project in projects)
    return "\n".join(lines)


def build_project_keyboard(projects: list[Project]) -> InlineKeyboardMarkup | None:
    if not projects:
        return None

    rows = []
    for project in projects:
        callback_data = f"project:show:{project.name}"
        if len(callback_data.encode("utf-8")) <= 64:
            rows.append([InlineKeyboardButton(project.name, callback_data=callback_data)])
    rows.append([InlineKeyboardButton("🗂 Последние задачи", callback_data="tasks:recent")])
    return InlineKeyboardMarkup(rows)


def build_project_details_message(project: Project) -> str:
    aliases = ", ".join(project.aliases) if project.aliases else "нет"
    stack = ", ".join(project.stack) if project.stack else "не настроен"
    return (
        f"Проект: {project.name}\n"
        f"Aliases: {aliases}\n"
        f"Stack: {stack}\n\n"
        "Чтобы создать задачу, отправь сообщение с упоминанием этого проекта.\n"
        f"Пример:\nВ {project.name} добавь ..."
    )


def build_status_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "Задачи ещё не созданы."
    return build_recent_tasks_message(tasks)
