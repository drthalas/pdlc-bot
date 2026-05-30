from app.project_registry import Project
from app.task_store import TaskRecord
from app.telegram_ui import (
    MENU_BUTTON,
    PROJECTS_BUTTON,
    STATUS_BUTTON,
    TASKS_BUTTON,
    build_persistent_menu_keyboard,
    build_project_details_message,
    build_project_keyboard,
    build_recent_tasks_keyboard,
    build_recent_tasks_message,
    build_start_message,
    build_task_actions_keyboard,
    get_menu_action,
)


def make_task(task_id: str, project_name: str | None = "pdlc-bot") -> TaskRecord:
    return TaskRecord(
        task_id=task_id,
        project_name=project_name,
        status="prompt_ready",
        workspace_path=f"tasks/{task_id}",
        created_at="2026-05-30T00:00:00+00:00",
    )


def button_data(markup) -> list[str]:
    return [button.callback_data for row in markup.inline_keyboard for button in row]


def button_text(markup) -> list[str]:
    return [button.text for row in markup.inline_keyboard for button in row]


def keyboard_text(markup) -> list[str]:
    return [button.text for row in markup.keyboard for button in row]


def test_start_message_mentions_main_actions():
    message = build_start_message()

    assert "PDLC Bot is running." in message
    assert "Choose an action:" in message


def test_persistent_menu_keyboard_contains_navigation_buttons():
    markup = build_persistent_menu_keyboard()

    texts = keyboard_text(markup)
    assert MENU_BUTTON in texts
    assert PROJECTS_BUTTON in texts
    assert TASKS_BUTTON in texts
    assert STATUS_BUTTON in texts
    assert markup.resize_keyboard is True


def test_get_menu_action_recognizes_menu_buttons():
    assert get_menu_action(MENU_BUTTON) == "menu"
    assert get_menu_action(PROJECTS_BUTTON) == "projects"
    assert get_menu_action(TASKS_BUTTON) == "tasks"
    assert get_menu_action(STATUS_BUTTON) == "status"
    assert get_menu_action("В pdlc-bot добавь кнопку") is None


def test_recent_tasks_message_with_tasks():
    message = build_recent_tasks_message([make_task("TASK-0002"), make_task("TASK-0001")])

    assert "Recent tasks:" in message
    assert "TASK-0002 — pdlc-bot — prompt_ready" in message
    assert "TASK-0001 — pdlc-bot — prompt_ready" in message


def test_recent_tasks_message_without_tasks():
    assert build_recent_tasks_message([]) == "No tasks created yet."


def test_callback_data_is_compact_and_contains_expected_ids():
    markup = build_task_actions_keyboard("TASK-0002")

    data = button_data(markup)
    assert "task:details:TASK-0002" in data
    assert "task:prompt:TASK-0002" in data
    assert "tasks:recent" in data
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


def test_task_actions_keyboard_contains_expected_buttons():
    markup = build_task_actions_keyboard("TASK-0002")

    texts = button_text(markup)
    assert "📄 Task details" in texts
    assert "🧠 Codex prompt" in texts
    assert "🗂 Recent tasks" in texts


def test_recent_tasks_keyboard_contains_task_buttons():
    markup = build_recent_tasks_keyboard([make_task("TASK-0002"), make_task("TASK-0001")])

    assert button_text(markup) == ["TASK-0002", "TASK-0001"]
    assert button_data(markup) == ["task:details:TASK-0002", "task:details:TASK-0001"]


def test_project_keyboard_contains_projects():
    projects = [
        Project(name="pdlc-bot", aliases=["pdlc"]),
        Project(name="example-api", aliases=["api"]),
    ]

    markup = build_project_keyboard(projects)

    assert "pdlc-bot" in button_text(markup)
    assert "example-api" in button_text(markup)
    assert "project:show:pdlc-bot" in button_data(markup)
    assert "project:show:example-api" in button_data(markup)
    assert all(len(item.encode("utf-8")) <= 64 for item in button_data(markup))


def test_project_details_message():
    project = Project(
        name="pdlc-bot",
        aliases=["pdlc", "бот задач"],
        stack=["Python", "Telegram Bot", "SQLite"],
    )

    message = build_project_details_message(project)

    assert "Project: pdlc-bot" in message
    assert "Aliases: pdlc, бот задач" in message
    assert "Stack: Python, Telegram Bot, SQLite" in message
