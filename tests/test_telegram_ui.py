import asyncio

from app.project_registry import Project
from app.task_store import TaskRecord
from app.telegram_bot import handle_callback, handle_text
from app.telegram_ui import (
    MENU_BUTTON,
    PROJECTS_BUTTON,
    RUNBOOK_BUTTON,
    STATUS_BUTTON,
    TASKS_BUTTON,
    build_main_menu_keyboard,
    build_persistent_menu_keyboard,
    build_project_details_message,
    build_project_keyboard,
    build_recent_tasks_keyboard,
    build_recent_tasks_message,
    build_runbook_message,
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


class FakeUser:
    id = 123


class FakeMessage:
    def __init__(self, text: str):
        self.text = text
        self.replies = []

    async def reply_text(self, text: str, reply_markup=None):
        self.replies.append({"text": text, "reply_markup": reply_markup})


class FakeUpdate:
    def __init__(self, text: str):
        self.effective_user = FakeUser()
        self.message = FakeMessage(text)


class FakeContext:
    class Application:
        bot_data = {"orchestrator": object()}

    application = Application()


class FakeCallbackQuery:
    def __init__(self, data: str):
        self.data = data
        self.answers = []
        self.edits = []

    async def answer(self, text=None):
        self.answers.append(text)

    async def edit_message_text(self, text: str, reply_markup=None):
        self.edits.append({"text": text, "reply_markup": reply_markup})


class FakeCallbackUpdate:
    message = None

    def __init__(self, data: str):
        self.effective_user = FakeUser()
        self.callback_query = FakeCallbackQuery(data)


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
    assert RUNBOOK_BUTTON not in texts
    assert markup.resize_keyboard is True


def test_get_menu_action_recognizes_menu_buttons():
    assert get_menu_action(MENU_BUTTON) == "menu"
    assert get_menu_action(PROJECTS_BUTTON) == "projects"
    assert get_menu_action(TASKS_BUTTON) == "tasks"
    assert get_menu_action(STATUS_BUTTON) == "status"
    assert get_menu_action(RUNBOOK_BUTTON) == "runbook"
    assert get_menu_action("В pdlc-bot добавь кнопку") is None


def test_main_menu_keyboard_contains_runbook_action():
    markup = build_main_menu_keyboard()

    assert "📘 Runbook" in button_text(markup)
    assert "runbook:show" in button_data(markup)


def test_runbook_message_contains_short_operational_help():
    message = build_runbook_message()

    assert "docs/MAC_MINI_RUNBOOK.md" in message
    assert "service status" in message
    assert "logs" in message
    assert "restart" in message
    assert "deployed version check" in message
    assert "ssh hermes-mini" not in message
    assert ".env" not in message


def test_handle_text_routes_runbook_button_without_creating_task(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    update = FakeUpdate(RUNBOOK_BUTTON)

    asyncio.run(handle_text(update, FakeContext()))

    assert len(update.message.replies) == 1
    assert "Mac mini runbook:" in update.message.replies[0]["text"]
    assert update.message.replies[0]["reply_markup"] is not None


def test_handle_callback_routes_runbook_action(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    update = FakeCallbackUpdate("runbook:show")

    asyncio.run(handle_callback(update, FakeContext()))

    assert update.callback_query.answers == [None]
    assert len(update.callback_query.edits) == 1
    assert "Mac mini runbook:" in update.callback_query.edits[0]["text"]


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
    assert "task:run_codex:TASK-0002" in data
    assert "task:details:TASK-0002" in data
    assert "task:prompt:TASK-0002" in data
    assert "tasks:recent" in data
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


def test_task_actions_keyboard_contains_expected_buttons():
    markup = build_task_actions_keyboard("TASK-0002")

    texts = button_text(markup)
    assert "▶️ Run Codex" in texts
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
