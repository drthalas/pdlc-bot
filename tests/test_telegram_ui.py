import asyncio
from pathlib import Path
from types import SimpleNamespace

from app.project_registry import Project
from app.post_run_controls import (
    TASK_RESULT_COMMITTED,
    TASK_RESULT_READY_FOR_POST_RUN_ACTIONS,
    PostRunActionResult,
    task_result_state,
)
from app.task_store import TaskRecord
from app.telegram_bot import handle_callback, handle_text, prompt, task
from app.telegram_ui import (
    MENU_BUTTON,
    PROJECTS_BUTTON,
    RUNBOOK_BUTTON,
    STATUS_BUTTON,
    TASKS_BUTTON,
    build_archived_tasks_keyboard,
    build_archived_tasks_message,
    build_codex_post_run_keyboard,
    build_commit_confirm_keyboard,
    build_discard_confirm_keyboard,
    build_main_menu_keyboard,
    build_persistent_menu_keyboard,
    build_project_details_message,
    build_project_keyboard,
    build_push_branch_keyboard,
    build_push_confirm_keyboard,
    build_recent_tasks_keyboard,
    build_recent_tasks_message,
    build_runbook_message,
    build_start_message,
    build_task_action_keyboard,
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


def make_task_with_input(tmp_path: Path, task_id: str, text: str, project_name: str | None = "pdlc-bot") -> TaskRecord:
    workspace = tmp_path / task_id
    workspace.mkdir()
    (workspace / "input.md").write_text(text, encoding="utf-8")
    return TaskRecord(
        task_id=task_id,
        project_name=project_name,
        status="prompt_ready",
        workspace_path=str(workspace),
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


class FakeStore:
    def __init__(self, record: TaskRecord, records: list[TaskRecord] | None = None):
        self.record = record
        self.records = records or [record]
        self.status_updates = []

    def get_task(self, task_id: str):
        return self.record if task_id == self.record.task_id else None

    def list_tasks(self, limit: int = 10, offset: int = 0):
        return self.records[offset : offset + limit]

    def update_status(self, task_id: str, status: str):
        self.status_updates.append((task_id, status))
        if task_id == self.record.task_id:
            self.record = TaskRecord(
                task_id=self.record.task_id,
                project_name=self.record.project_name,
                status=status,
                workspace_path=self.record.workspace_path,
                created_at=self.record.created_at,
            )
        return True


def make_callback_context(record: TaskRecord, args: list[str] | None = None):
    return SimpleNamespace(
        args=args or [],
        application=SimpleNamespace(bot_data={"orchestrator": SimpleNamespace(store=FakeStore(record))}),
    )


def make_records_callback_context(records: list[TaskRecord]):
    record = records[0]
    return SimpleNamespace(
        args=[],
        application=SimpleNamespace(bot_data={"orchestrator": SimpleNamespace(store=FakeStore(record, records=records))}),
    )


def write_successful_post_run_artifacts(workspace: Path) -> None:
    workspace.mkdir()
    (workspace / "codex_exit_code.txt").write_text("0\n", encoding="utf-8")
    (workspace / "diff.patch").write_text("diff --git a/app.py b/app.py\n+change\n", encoding="utf-8")
    (workspace / "test_report.md").write_text("Exit code: 0\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("Use Codex.\n", encoding="utf-8")


def test_start_message_mentions_main_actions():
    message = build_start_message()

    assert "PDLC Bot работает." in message
    assert "Выбери действие:" in message


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
    assert "статус сервиса" in message
    assert "логи" in message
    assert "restart" in message
    assert "проверка deployed version" in message
    assert "ssh hermes-mini" not in message
    assert ".env" not in message


def test_handle_text_routes_runbook_button_without_creating_task(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    update = FakeUpdate(RUNBOOK_BUTTON)

    asyncio.run(handle_text(update, FakeContext()))

    assert len(update.message.replies) == 1
    assert "Runbook для Mac mini:" in update.message.replies[0]["text"]
    assert update.message.replies[0]["reply_markup"] is not None


def test_handle_callback_routes_runbook_action(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    update = FakeCallbackUpdate("runbook:show")

    asyncio.run(handle_callback(update, FakeContext()))

    assert update.callback_query.answers == [None]
    assert len(update.callback_query.edits) == 1
    assert "Runbook для Mac mini:" in update.callback_query.edits[0]["text"]


def test_handle_callback_shows_post_run_keyboard_after_successful_codex_run(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord(
        task_id="TASK-0013",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )
    monkeypatch.setattr("app.telegram_bot.build_codex_runner_response", lambda task: "Codex Runner codex_run mode.\nCodex finished.")
    update = FakeCallbackUpdate("task:run_codex:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    markup = update.callback_query.edits[-1]["reply_markup"]
    assert "🔍 Показать diff" in button_text(markup)
    assert "✅ Закоммитить изменения" in button_text(markup)


def test_handle_callback_confirm_commit_shows_push_button_after_mocked_commit(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    workspace.mkdir()
    record = TaskRecord(
        task_id="TASK-0013",
        project_name="pdlc-bot",
        status="prompt_ready",
        workspace_path=str(workspace),
        created_at="2026-05-30T00:00:00+00:00",
    )
    monkeypatch.setattr(
        "app.telegram_bot.commit_task_changes",
        lambda task: PostRunActionResult(True, "Committed local changes.", branch_name="agent/TASK-0013-post-run"),
    )
    update = FakeCallbackUpdate("task:confirm_commit:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    assert "Committed local changes." in update.callback_query.edits[-1]["text"]
    assert "📤 Отправить branch" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_recent_tasks_message_with_tasks(tmp_path):
    first = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot улучши генерацию prompt и список задач")
    second = make_task_with_input(tmp_path, "TASK-0001", "pdlc-bot добавить кнопки")

    message = build_recent_tasks_message([first, second])

    assert "Последние задачи:" in message
    assert "TASK-0002 — pdlc-bot — улучши генерацию prompt и список задач" in message
    assert "TASK-0001 — pdlc-bot — добавить кнопки" in message


def test_recent_tasks_message_without_tasks():
    assert build_recent_tasks_message([]) == "Задачи ещё не созданы."


def test_recent_tasks_message_missing_input_falls_back_to_task_id(tmp_path):
    workspace = tmp_path / "TASK-0002"
    workspace.mkdir()
    record = TaskRecord(
        "TASK-0002",
        "pdlc-bot",
        "prompt_ready",
        str(workspace),
        "2026-05-30T00:00:00+00:00",
    )
    message = build_recent_tasks_message([record])

    assert "TASK-0002 — pdlc-bot — TASK-0002" in message


def test_recent_tasks_message_truncates_long_title(tmp_path):
    record = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot " + "очень " * 30)

    message = build_recent_tasks_message([record])

    assert "…" in message


def test_recent_tasks_message_limits_to_ten_and_mentions_archive(tmp_path):
    records = [
        make_task_with_input(tmp_path, f"TASK-{index:04d}", f"В pdlc-bot задача {index}")
        for index in range(12, 0, -1)
    ]

    message = build_recent_tasks_message(records)
    markup = build_recent_tasks_keyboard(records)

    assert "TASK-0012" in message
    assert "TASK-0003" in message
    assert "TASK-0002" not in message
    assert "Более старые задачи доступны в архиве." in message
    assert "📦 Архив задач" in button_text(markup)
    assert "tasks:archive" in button_data(markup)
    assert len([text for text in button_text(markup) if text.startswith("TASK-")]) == 10


def test_archived_tasks_message_and_keyboard_show_older_tasks(tmp_path):
    records = [
        make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot старая задача"),
        make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot самая старая задача"),
    ]

    message = build_archived_tasks_message(records)
    markup = build_archived_tasks_keyboard(records)

    assert "📦 Архив задач:" in message
    assert "TASK-0002 — pdlc-bot — старая задача" in message
    assert "🗂 Последние задачи" in button_text(markup)


def test_callback_data_is_compact_and_contains_expected_ids():
    markup = build_task_actions_keyboard("TASK-0002")

    data = button_data(markup)
    assert "task:run_codex:TASK-0002" in data
    assert "task:details:TASK-0002" in data
    assert "task:prompt:TASK-0002" in data
    assert "task:artifacts:TASK-0002" in data
    assert "tasks:recent" in data
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


def test_task_actions_keyboard_contains_expected_buttons():
    markup = build_task_actions_keyboard("TASK-0002")

    texts = button_text(markup)
    assert "▶️ Запустить Codex" in texts
    assert "📄 Детали задачи" in texts
    assert "🧠 Codex prompt" in texts
    assert "🛠 Технические детали" in texts
    assert "🗂 Последние задачи" in texts


def test_codex_post_run_keyboard_contains_safe_first_layer_actions():
    markup = build_codex_post_run_keyboard("TASK-0013")

    texts = button_text(markup)
    data = button_data(markup)
    assert "🔍 Показать diff" in texts
    assert "🧪 Запустить тесты ещё раз" in texts
    assert "✅ Закоммитить изменения" in texts
    assert "🧹 Откатить изменения" in texts
    assert "task:show_diff:TASK-0013" in data
    assert "task:tests_again:TASK-0013" in data
    assert "task:commit:TASK-0013" in data
    assert "task:discard:TASK-0013" in data
    assert "task:artifacts:TASK-0013" in data
    assert "tasks:recent" in data
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


def test_task_result_state_ready_for_post_run_actions(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = make_task("TASK-0013")
    record = TaskRecord(record.task_id, record.project_name, record.status, str(workspace), record.created_at)

    assert task_result_state(record) == TASK_RESULT_READY_FOR_POST_RUN_ACTIONS


def test_task_action_keyboard_prompt_ready_shows_run_codex():
    markup = build_task_action_keyboard(make_task("TASK-0002"))

    texts = button_text(markup)
    assert "▶️ Запустить Codex" in texts
    assert "🔍 Показать diff" not in texts


def test_task_action_keyboard_after_codex_run_shows_post_run_controls(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")

    markup = build_task_action_keyboard(record)
    texts = button_text(markup)

    assert task_result_state(record) == TASK_RESULT_READY_FOR_POST_RUN_ACTIONS
    assert "🔍 Показать diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_task_action_keyboard_committed_shows_push_branch(tmp_path):
    record = TaskRecord("TASK-0013", "pdlc-bot", "committed", str(tmp_path / "TASK-0013"), "2026-05-30T00:00:00+00:00")

    markup = build_task_action_keyboard(record)

    assert task_result_state(record) == TASK_RESULT_COMMITTED
    assert button_text(markup) == ["📤 Отправить branch", "🛠 Технические детали", "🗂 Последние задачи"]


def test_show_diff_callback_keeps_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:show_diff:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    assert "Diff for TASK-0013" in update.callback_query.edits[-1]["text"]
    assert "🔍 Показать diff" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_run_tests_again_callback_keeps_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:tests_again:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    assert "Повторный запуск тестов пока не реализован." in update.callback_query.edits[-1]["text"]
    assert "🔍 Показать diff" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_task_details_after_codex_run_shows_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:details:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    texts = button_text(update.callback_query.edits[-1]["reply_markup"])
    assert "🔍 Показать diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_task_artifacts_callback_shows_technical_files(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0018"
    workspace.mkdir()
    (workspace / "input.md").write_text("В pdlc-bot улучшить карточку задачи\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("prompt\n", encoding="utf-8")
    record = TaskRecord("TASK-0018", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:artifacts:TASK-0018")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    text = update.callback_query.edits[-1]["text"]
    assert "🛠 Технические детали TASK-0018" in text
    assert "- input.md" in text
    assert "- codex_prompt.md" in text


def test_archive_callback_shows_older_tasks(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [
        make_task_with_input(tmp_path, f"TASK-{index:04d}", f"В pdlc-bot задача {index}")
        for index in range(12, 0, -1)
    ]
    update = FakeCallbackUpdate("tasks:archive")

    asyncio.run(handle_callback(update, make_records_callback_context(records)))

    text = update.callback_query.edits[-1]["text"]
    assert "📦 Архив задач:" in text
    assert "TASK-0002" in text
    assert "TASK-0012" not in text


def test_task_command_after_codex_run_shows_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeUpdate("/task TASK-0013")

    asyncio.run(task(update, make_callback_context(record, args=["TASK-0013"])))

    texts = button_text(update.message.replies[-1]["reply_markup"])
    assert "🔍 Показать diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_prompt_after_codex_run_shows_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeUpdate("/prompt TASK-0013")

    asyncio.run(prompt(update, make_callback_context(record, args=["TASK-0013"])))

    texts = button_text(update.message.replies[-1]["reply_markup"])
    assert "🔍 Показать diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_task_action_keyboard_running_shows_running_state(tmp_path):
    record = TaskRecord("TASK-0015", "pdlc-bot", "codex_running", str(tmp_path / "TASK-0015"), "2026-05-30T00:00:00+00:00")

    markup = build_task_action_keyboard(record)

    assert task_result_state(record) == "running"
    assert button_text(markup) == ["⏳ Выполняется", "🛠 Технические детали", "🗂 Последние задачи"]


def test_task_action_callback_data_is_compact_for_all_states(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    records = [
        make_task("TASK-0002"),
        TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00"),
        TaskRecord("TASK-0014", "pdlc-bot", "committed", str(tmp_path / "TASK-0014"), "2026-05-30T00:00:00+00:00"),
        TaskRecord("TASK-0015", "pdlc-bot", "codex_running", str(tmp_path / "TASK-0015"), "2026-05-30T00:00:00+00:00"),
    ]

    for record in records:
        assert all(len(item.encode("utf-8")) <= 64 for item in button_data(build_task_action_keyboard(record)))


def test_confirm_keyboards_separate_commit_push_and_discard():
    assert button_data(build_commit_confirm_keyboard("TASK-0013")) == [
        "task:confirm_commit:TASK-0013",
        "task:details:TASK-0013",
    ]
    assert button_data(build_push_branch_keyboard("TASK-0013")) == [
        "task:push:TASK-0013",
        "task:details:TASK-0013",
    ]
    assert button_data(build_push_confirm_keyboard("TASK-0013")) == [
        "task:confirm_push:TASK-0013",
        "task:details:TASK-0013",
    ]
    assert button_data(build_discard_confirm_keyboard("TASK-0013")) == [
        "task:confirm_discard:TASK-0013",
        "task:details:TASK-0013",
    ]


def test_recent_tasks_keyboard_contains_task_buttons(tmp_path):
    first = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot улучшить список задач")
    second = make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot добавить кнопки")
    markup = build_recent_tasks_keyboard([first, second])

    assert button_text(markup) == ["TASK-0002 — улучшить список задач", "TASK-0001 — добавить кнопки"]
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

    assert "Проект: pdlc-bot" in message
    assert "Aliases: pdlc, бот задач" in message
    assert "Stack: Python, Telegram Bot, SQLite" in message
