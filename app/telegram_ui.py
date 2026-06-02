from __future__ import annotations

from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.post_run_controls import (
    TASK_RESULT_COMMITTED,
    TASK_RESULT_READY_FOR_POST_RUN_ACTIONS,
    TASK_RESULT_RUNNING,
    task_result_state,
)
from app.project_registry import Project
from app.task_store import TaskRecord
from app.task_messages import task_status_display, task_title


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
PROJECT_TASKS_PREVIEW_LIMIT = 5
TASK_BUTTON_TITLE_LIMIT = 40
LONG_BUTTON_LABELS = (
    "Показать diff",
    "Запустить тесты ещё раз",
    "Закоммитить изменения",
    "Откатить изменения",
    "Технические детали",
    "Последние задачи",
    "Отправить branch",
    "Детали задачи",
    "Архив задач",
)

MENU_ACTIONS = {
    MENU_BUTTON: "menu",
    LEGACY_MENU_BUTTON: "menu",
    "Меню": "menu",
    "Menu": "menu",
    PROJECTS_BUTTON: "projects",
    LEGACY_PROJECTS_BUTTON: "projects",
    "Проекты": "projects",
    "Projects": "projects",
    TASKS_BUTTON: "tasks",
    LEGACY_TASKS_BUTTON: "tasks",
    "🗂 Последние": "tasks",
    "🗂 Последние задачи": "tasks",
    "🗂 Recent tasks": "tasks",
    "Задачи": "tasks",
    "Tasks": "tasks",
    "Последние": "tasks",
    "Последние задачи": "tasks",
    "Recent tasks": "tasks",
    STATUS_BUTTON: "status",
    LEGACY_STATUS_BUTTON: "status",
    "Статус": "status",
    "Status": "status",
    RUNBOOK_BUTTON: "runbook",
}


def get_menu_action(text: str) -> str | None:
    normalized = " ".join(text.strip().split())
    return MENU_ACTIONS.get(normalized)


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
                InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
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
                InlineKeyboardButton("📄 Детали", callback_data=f"task:details:{task_id}"),
                InlineKeyboardButton("🧠 Codex prompt", callback_data=f"task:prompt:{task_id}"),
            ],
            [InlineKeyboardButton("🛠 Детали", callback_data=f"task:artifacts:{task_id}")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="tasks:recent"),
                InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
                InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
            ],
        ]
    )


def build_task_actions_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return build_prompt_ready_task_keyboard(task_id)


def build_task_details_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("▶️ Запустить Codex", callback_data=f"task:run_codex:{task_id}")],
            [InlineKeyboardButton("🧠 Codex prompt", callback_data=f"task:prompt:{task_id}")],
            [InlineKeyboardButton("🛠 Детали", callback_data=f"task:artifacts:{task_id}")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="tasks:recent"),
                InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
                InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
            ],
        ]
    )


def build_codex_post_run_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔍 Diff", callback_data=f"task:show_diff:{task_id}"),
                InlineKeyboardButton("🧪 Тесты", callback_data=f"task:tests_again:{task_id}"),
            ],
            [
                InlineKeyboardButton("✅ Коммит", callback_data=f"task:commit:{task_id}"),
                InlineKeyboardButton("🧹 Откат", callback_data=f"task:discard:{task_id}"),
            ],
            [InlineKeyboardButton("🛠 Детали", callback_data=f"task:artifacts:{task_id}")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="tasks:recent"),
                InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
                InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
            ],
        ]
    )


def build_committed_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📤 Push", callback_data=f"task:push:{task_id}")],
            [InlineKeyboardButton("🛠 Детали", callback_data=f"task:artifacts:{task_id}")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="tasks:recent"),
                InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
                InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
            ],
        ]
    )


def build_running_task_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⏳ Выполняется", callback_data=f"task:details:{task_id}")],
            [InlineKeyboardButton("🛠 Детали", callback_data=f"task:artifacts:{task_id}")],
            [
                InlineKeyboardButton("⬅️ Назад", callback_data="tasks:recent"),
                InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
                InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
            ],
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
                InlineKeyboardButton("✅ Подтвердить", callback_data=f"task:confirm_commit:{task_id}"),
                InlineKeyboardButton("⬅️ Назад", callback_data=f"task:details:{task_id}"),
            ],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu:show")],
        ]
    )


def build_push_branch_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📤 Push", callback_data=f"task:push:{task_id}"),
                InlineKeyboardButton("📄 Детали", callback_data=f"task:details:{task_id}"),
            ],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu:show")],
        ]
    )


def build_push_confirm_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📤 Подтвердить", callback_data=f"task:confirm_push:{task_id}"),
                InlineKeyboardButton("⬅️ Назад", callback_data=f"task:details:{task_id}"),
            ],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu:show")],
        ]
    )


def build_discard_confirm_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🧹 Подтвердить", callback_data=f"task:confirm_discard:{task_id}"),
                InlineKeyboardButton("⬅️ Назад", callback_data=f"task:details:{task_id}"),
            ],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu:show")],
        ]
    )


def build_task_subview_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Назад", callback_data=f"task:details:{task_id}")],
            [
                InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
                InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
            ],
        ]
    )


def _visible_recent_tasks(tasks: list[TaskRecord]) -> list[TaskRecord]:
    return tasks[:RECENT_TASKS_LIMIT]


def _has_archive(tasks: list[TaskRecord]) -> bool:
    return len(tasks) > RECENT_TASKS_LIMIT


def build_task_button_label(task: TaskRecord) -> str:
    status_emoji = task_status_display(task)[0]
    title = task_title(task, limit=TASK_BUTTON_TITLE_LIMIT)
    if title == task.task_id:
        return f"{status_emoji} {task.task_id}"
    return f"{status_emoji} {task.task_id} — {title}"


def build_recent_tasks_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "Задачи ещё не созданы."

    lines = ["🗂 Последние задачи", "", "Открой задачу кнопкой ниже."]
    if _has_archive(tasks):
        lines.append("Более старые задачи доступны в архиве.")
    return "\n".join(lines)


def build_recent_tasks_keyboard(tasks: list[TaskRecord], include_archive: bool | None = None) -> InlineKeyboardMarkup | None:
    if not tasks:
        return None
    rows = [
        [InlineKeyboardButton(build_task_button_label(task), callback_data=f"task:details:{task.task_id}")]
        for task in _visible_recent_tasks(tasks)
    ]
    if include_archive is None:
        include_archive = _has_archive(tasks)
    if include_archive:
        rows.append([InlineKeyboardButton("📦 Архив", callback_data="tasks:archive")])
    rows.append([InlineKeyboardButton("🏠 Меню", callback_data="menu:show")])
    return InlineKeyboardMarkup(
        rows
    )


def build_archived_tasks_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "В архиве пока нет задач."

    return "📦 Архив задач\n\nОткрой задачу кнопкой ниже."


def build_archived_tasks_keyboard(tasks: list[TaskRecord]) -> InlineKeyboardMarkup | None:
    rows = [
        [InlineKeyboardButton(build_task_button_label(task), callback_data=f"task:details:{task.task_id}")]
        for task in tasks
    ]
    rows.append([InlineKeyboardButton("⬅️ Назад", callback_data="tasks:recent")])
    rows.append(
        [
            InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent"),
            InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def _project_description(project: Project) -> str:
    return project.description or "Описание не указано."


def _project_local_status(project: Project) -> str:
    if not project.local_path:
        return "local_path не указан"
    return "локальная папка доступна" if Path(project.local_path).exists() else "локальная папка не найдена"


def _project_tasks(project: Project, tasks: list[TaskRecord] | None) -> list[TaskRecord]:
    if not tasks:
        return []
    project_name = project.name.casefold()
    return [task for task in tasks if (task.project_name or "").casefold() == project_name]


def build_projects_message(projects: list[Project], tasks: list[TaskRecord] | None = None) -> str:
    if not projects:
        return "Проекты не настроены. Сначала создай config/projects.yaml."

    lines = ["📋 Проекты:", ""]
    for project in projects:
        project_tasks = _project_tasks(project, tasks)
        lines.extend(
            [
                f"• {project.name}",
                f"  Описание: {_project_description(project)}",
                f"  GitHub URL: {project.repo_url or 'не указан'}",
                f"  Статус: {_project_local_status(project)}",
                f"  Задач: {len(project_tasks)}",
                "",
            ]
        )
    return "\n".join(lines)


def build_project_keyboard(projects: list[Project]) -> InlineKeyboardMarkup:
    rows = []
    for project in projects:
        callback_data = f"project:show:{project.name}"
        if len(callback_data.encode("utf-8")) <= 64:
            rows.append([InlineKeyboardButton(f"📁 {project.name}", callback_data=callback_data)])
    rows.append([InlineKeyboardButton("➕ Добавить проект", callback_data="projects:add")])
    rows.append([InlineKeyboardButton("🗂 Последние", callback_data="tasks:recent")])
    return InlineKeyboardMarkup(rows)


def build_project_details_message(project: Project, tasks: list[TaskRecord] | None = None) -> str:
    aliases = ", ".join(project.aliases) if project.aliases else "нет"
    stack = ", ".join(project.stack) if project.stack else "не настроен"
    project_tasks = _project_tasks(project, tasks)
    lines = [
        f"📁 Карточка проекта: {project.name}",
        "",
        f"Описание: {_project_description(project)}",
        f"GitHub URL: {project.repo_url or 'не указан'}",
        f"Local path: {project.local_path or 'не указан'}",
        f"Статус: {_project_local_status(project)}",
        f"Алиасы: {aliases}",
        f"Стек: {stack}",
        f"Задач: {len(project_tasks)}",
        "",
        "Задачи проекта открываются кнопкой ниже.",
    ]
    if not project_tasks:
        lines.append("Задач для этого проекта пока нет.")
    return "\n".join(lines)


def build_project_details_keyboard(project: Project) -> InlineKeyboardMarkup:
    rows = []
    tasks_callback = f"project:tasks:{project.name}"
    if len(tasks_callback.encode("utf-8")) <= 64:
        rows.append([InlineKeyboardButton("🗂 Задачи проекта", callback_data=tasks_callback)])
    rows.append([InlineKeyboardButton("⬅️ Назад к проектам", callback_data="projects:show")])
    rows.append(
        [
            InlineKeyboardButton("➕ Добавить проект", callback_data="projects:add"),
            InlineKeyboardButton("🏠 Меню", callback_data="menu:show"),
        ]
    )
    return InlineKeyboardMarkup(rows)


def build_project_tasks_message(project: Project, tasks: list[TaskRecord] | None = None) -> str:
    project_tasks = _project_tasks(project, tasks)
    if not project_tasks:
        return f"Для проекта {project.name} пока нет задач."

    return f"🗂 Задачи проекта {project.name}\n\nОткрой задачу кнопкой ниже."


def build_project_tasks_keyboard(project: Project) -> InlineKeyboardMarkup:
    rows = []
    details_callback = f"project:show:{project.name}"
    if len(details_callback.encode("utf-8")) <= 64:
        rows.append([InlineKeyboardButton("📁 Проект", callback_data=details_callback)])
    rows.append([InlineKeyboardButton("⬅️ Назад к проектам", callback_data="projects:show")])
    rows.append([InlineKeyboardButton("🏠 Меню", callback_data="menu:show")])
    return InlineKeyboardMarkup(rows)


def build_project_task_buttons(project: Project, tasks: list[TaskRecord] | None = None) -> InlineKeyboardMarkup:
    project_tasks = _project_tasks(project, tasks)
    rows = [
        [InlineKeyboardButton(build_task_button_label(task), callback_data=f"task:details:{task.task_id}")]
        for task in project_tasks
    ]
    rows.extend(build_project_tasks_keyboard(project).inline_keyboard)
    return InlineKeyboardMarkup(rows)


def build_add_project_stub_message() -> str:
    return (
        "➕ Добавление проекта пока не реализовано.\n\n"
        "Будущий flow запросит описание, GitHub URL, local_path, aliases и stack, затем покажет предпросмотр перед сохранением.\n\n"
        "Сейчас бот ничего не клонирует и не меняет config/projects.yaml."
    )


def build_add_project_stub_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("⬅️ Назад к проектам", callback_data="projects:show")],
            [InlineKeyboardButton("🏠 Меню", callback_data="menu:show")],
        ]
    )


def build_status_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "Задачи ещё не созданы."
    return build_recent_tasks_message(tasks)
