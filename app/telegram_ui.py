from __future__ import annotations

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup

from app.project_registry import Project
from app.task_store import TaskRecord


MENU_BUTTON = "🏠 Menu"
PROJECTS_BUTTON = "📋 Projects"
TASKS_BUTTON = "🗂 Tasks"
STATUS_BUTTON = "ℹ️ Status"

MENU_ACTIONS = {
    MENU_BUTTON: "menu",
    PROJECTS_BUTTON: "projects",
    TASKS_BUTTON: "tasks",
    STATUS_BUTTON: "status",
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
        input_field_placeholder="Send a development task or use the menu",
    )


def build_start_message() -> str:
    return (
        "PDLC Bot is running.\n\n"
        "Use this bot to create development tasks and generate Codex-ready prompts.\n\n"
        "Choose an action:"
    )


def build_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📋 Projects", callback_data="projects:show"),
                InlineKeyboardButton("🗂 Recent tasks", callback_data="tasks:recent"),
            ],
            [InlineKeyboardButton("ℹ️ Status", callback_data="status:show")],
        ]
    )


def build_task_actions_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("▶️ Run Codex", callback_data=f"task:run_codex:{task_id}")],
            [
                InlineKeyboardButton("📄 Task details", callback_data=f"task:details:{task_id}"),
                InlineKeyboardButton("🧠 Codex prompt", callback_data=f"task:prompt:{task_id}"),
            ],
            [InlineKeyboardButton("🗂 Recent tasks", callback_data="tasks:recent")],
        ]
    )


def build_task_details_keyboard(task_id: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("▶️ Run Codex", callback_data=f"task:run_codex:{task_id}")],
            [InlineKeyboardButton("🧠 Codex prompt", callback_data=f"task:prompt:{task_id}")],
            [InlineKeyboardButton("🗂 Recent tasks", callback_data="tasks:recent")],
        ]
    )


def build_recent_tasks_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "No tasks created yet."

    lines = ["Recent tasks:", ""]
    for task in tasks:
        project_name = task.project_name or "not detected"
        lines.append(f"{task.task_id} — {project_name} — {task.status}")
    return "\n".join(lines)


def build_recent_tasks_keyboard(tasks: list[TaskRecord]) -> InlineKeyboardMarkup | None:
    if not tasks:
        return None
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton(task.task_id, callback_data=f"task:details:{task.task_id}")] for task in tasks]
    )


def build_projects_message(projects: list[Project]) -> str:
    if not projects:
        return "No projects configured. Create config/projects.yaml first."

    lines = ["Configured projects:", ""]
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
    rows.append([InlineKeyboardButton("🗂 Recent tasks", callback_data="tasks:recent")])
    return InlineKeyboardMarkup(rows)


def build_project_details_message(project: Project) -> str:
    aliases = ", ".join(project.aliases) if project.aliases else "none"
    stack = ", ".join(project.stack) if project.stack else "not configured"
    return (
        f"Project: {project.name}\n"
        f"Aliases: {aliases}\n"
        f"Stack: {stack}\n\n"
        "To create a task, send a message mentioning this project.\n"
        f"Example:\nВ {project.name} добавь ..."
    )


def build_status_message(tasks: list[TaskRecord]) -> str:
    if not tasks:
        return "No tasks created yet."
    return build_recent_tasks_message(tasks)
