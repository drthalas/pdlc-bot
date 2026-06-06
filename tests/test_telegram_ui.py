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
from app.telegram_bot import fix, handle_callback, handle_text, prompt, status, task, tasks
from app.telegram_ui import (
    LONG_BUTTON_LABELS,
    MENU_BUTTON,
    PROJECTS_BUTTON,
    RUNBOOK_BUTTON,
    STATUS_BUTTON,
    TASKS_BUTTON,
    LEGACY_MENU_BUTTON,
    LEGACY_PROJECTS_BUTTON,
    LEGACY_STATUS_BUTTON,
    LEGACY_TASKS_BUTTON,
    build_add_project_stub_keyboard,
    build_add_project_stub_message,
    build_codex_changes_requested_keyboard,
    build_archived_tasks_keyboard,
    build_archived_tasks_message,
    build_codex_post_run_keyboard,
    build_commit_confirm_keyboard,
    build_discard_confirm_keyboard,
    build_fix_prompt_ready_keyboard,
    build_main_menu_keyboard,
    build_persistent_menu_keyboard,
    build_project_details_keyboard,
    build_project_details_message,
    build_project_keyboard,
    build_project_task_buttons,
    build_project_tasks_keyboard,
    build_project_tasks_message,
    build_projects_message,
    build_push_branch_keyboard,
    build_push_confirm_keyboard,
    build_recent_tasks_keyboard,
    build_recent_tasks_message,
    build_runbook_message,
    build_start_message,
    build_task_action_keyboard,
    build_task_actions_keyboard,
    build_task_button_label,
    build_task_subview_keyboard,
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


def assert_readable_task_list_payload(payload, task_id: str, title: str) -> None:
    text = payload["text"]
    markup = payload["reply_markup"]

    assert text.strip() != "Действия с задачами:"
    assert "Действия с задачами:" not in text
    assert "Открой задачу кнопкой ниже." in text
    assert f"{task_id} — pdlc-bot" not in text
    assert title not in text
    assert markup is not None
    labels = button_text(markup)
    data = button_data(markup)
    assert any(label.startswith(f"⚪ {task_id} — ") for label in labels)
    assert any(title in label for label in labels)
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


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
    def __init__(self, orchestrator=None):
        self.application = SimpleNamespace(bot_data={"orchestrator": orchestrator or object()})

class RecordingOrchestrator:
    def __init__(self, records: list[TaskRecord] | None = None):
        self.created_texts = []
        self.store = FakeStore(records[0], records=records) if records else None

    def create_task(self, text: str):
        self.created_texts.append(text)
        return SimpleNamespace(
            response_text="created",
            record=TaskRecord("TASK-9999", "pdlc-bot", "prompt_ready", "tasks/TASK-9999", "2026-05-30T00:00:00+00:00"),
        )


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


class FakeRegistry:
    def __init__(self, projects: list[Project]):
        self.projects = projects

    def list_projects(self):
        return self.projects

    def get(self, name_or_alias: str):
        for project in self.projects:
            if project.name == name_or_alias or name_or_alias in project.aliases:
                return project
        return None


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


def make_project_callback_context(projects: list[Project], records: list[TaskRecord]):
    return SimpleNamespace(
        args=[],
        application=SimpleNamespace(
            bot_data={
                "orchestrator": SimpleNamespace(
                    registry=FakeRegistry(projects),
                    store=FakeStore(records[0], records=records),
                )
            }
        ),
    )


def write_successful_post_run_artifacts(workspace: Path) -> None:
    workspace.mkdir()
    (workspace / "branch_name.txt").write_text("agent/TASK-0013-post-run\n", encoding="utf-8")
    (workspace / "input.md").write_text("В pdlc-bot улучшить post-run UX\n", encoding="utf-8")
    (workspace / "codex_exit_code.txt").write_text("0\n", encoding="utf-8")
    (workspace / "diff.patch").write_text("diff --git a/app.py b/app.py\n+change\n", encoding="utf-8")
    (workspace / "test_report.md").write_text("Exit code: 0\n", encoding="utf-8")
    (workspace / "codex_prompt.md").write_text("Use Codex.\n", encoding="utf-8")


def write_changes_requested_review_report(workspace: Path) -> None:
    (workspace / "review_report.md").write_text(
        "# Review report: TASK-0013\n\n"
        "Status: changes_requested\n\n"
        "Summary:\n"
        "Reviewer found blocking issues.\n",
        encoding="utf-8",
    )


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
    assert get_menu_action(LEGACY_MENU_BUTTON) == "menu"
    assert get_menu_action("Меню") == "menu"
    assert get_menu_action(PROJECTS_BUTTON) == "projects"
    assert get_menu_action(LEGACY_PROJECTS_BUTTON) == "projects"
    assert get_menu_action("Projects") == "projects"
    assert get_menu_action(TASKS_BUTTON) == "tasks"
    assert get_menu_action(LEGACY_TASKS_BUTTON) == "tasks"
    assert get_menu_action("🗂 Последние") == "tasks"
    assert get_menu_action("🗂 Recent tasks") == "tasks"
    assert get_menu_action("Задачи") == "tasks"
    assert get_menu_action("Tasks") == "tasks"
    assert get_menu_action(STATUS_BUTTON) == "status"
    assert get_menu_action(LEGACY_STATUS_BUTTON) == "status"
    assert get_menu_action("Статус") == "status"
    assert get_menu_action(RUNBOOK_BUTTON) == "runbook"
    assert get_menu_action("В pdlc-bot добавь кнопку") is None


def test_handle_text_routes_legacy_tasks_button_without_creating_task(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot тестовая задача")]
    orchestrator = RecordingOrchestrator(records=records)
    update = FakeUpdate(LEGACY_TASKS_BUTTON)

    asyncio.run(handle_text(update, FakeContext(orchestrator)))

    assert orchestrator.created_texts == []
    assert len(update.message.replies) == 1
    assert "🗂 Последние задачи" in update.message.replies[0]["text"]
    assert "тестовая задача" not in update.message.replies[0]["text"]
    assert button_text(update.message.replies[0]["reply_markup"]) == ["⚪ TASK-0001 — тестовая задача", "🏠 Меню"]


def test_handle_text_routes_new_tasks_button_without_creating_task(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot тестовая задача")]
    orchestrator = RecordingOrchestrator(records=records)
    update = FakeUpdate(TASKS_BUTTON)

    asyncio.run(handle_text(update, FakeContext(orchestrator)))

    assert orchestrator.created_texts == []
    assert len(update.message.replies) == 1
    assert "🗂 Последние задачи" in update.message.replies[0]["text"]
    assert "тестовая задача" not in update.message.replies[0]["text"]
    assert button_text(update.message.replies[0]["reply_markup"]) == ["⚪ TASK-0001 — тестовая задача", "🏠 Меню"]


def test_handle_text_regular_text_still_creates_task(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    orchestrator = RecordingOrchestrator()
    update = FakeUpdate("В pdlc-bot добавь кнопку")

    asyncio.run(handle_text(update, FakeContext(orchestrator)))

    assert orchestrator.created_texts == ["В pdlc-bot добавь кнопку"]
    assert update.message.replies[0]["text"] == "created"


def test_tasks_command_sends_text_list_and_inline_keyboard_together(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot улучшить список задач")]
    update = FakeUpdate("/tasks")

    asyncio.run(tasks(update, FakeContext(RecordingOrchestrator(records=records))))

    assert len(update.message.replies) == 1
    assert "🗂 Последние задачи" in update.message.replies[0]["text"]
    assert "улучшить список задач" not in update.message.replies[0]["text"]
    assert button_text(update.message.replies[0]["reply_markup"]) == ["⚪ TASK-0001 — улучшить список задач", "🏠 Меню"]


def test_status_command_sends_text_list_and_inline_keyboard_together(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot проверить статус")]
    update = FakeUpdate("/status")

    asyncio.run(status(update, FakeContext(RecordingOrchestrator(records=records))))

    assert len(update.message.replies) == 1
    assert "проверить статус" not in update.message.replies[0]["text"]
    assert button_text(update.message.replies[0]["reply_markup"]) == ["⚪ TASK-0001 — проверить статус", "🏠 Меню"]


def test_tasks_command_live_scenario_shows_titles_status_and_archive_button(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [
        make_task_with_input(tmp_path, f"TASK-{index:04d}", f"В pdlc-bot задача номер {index}")
        for index in range(12, 0, -1)
    ]
    update = FakeUpdate("/tasks")

    asyncio.run(tasks(update, FakeContext(RecordingOrchestrator(records=records))))

    reply = update.message.replies[0]
    assert len(update.message.replies) == 1
    assert "Действия с задачами:" not in reply["text"]
    assert "TASK-0012 — pdlc-bot" not in reply["text"]
    assert "задача номер 12" not in reply["text"]
    assert "Статус:" not in reply["text"]
    assert "TASK-0002" not in reply["text"]
    assert "📦 Архив" in button_text(reply["reply_markup"])
    assert "⚪ TASK-0012 — задача номер 12" in button_text(reply["reply_markup"])
    assert all("задача номер" in text or not text.startswith("⚪ TASK-") for text in button_text(reply["reply_markup"]))


def test_live_task_list_routes_all_send_readable_text(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [
        make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot улучшить список задач"),
        make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot добавить кнопку"),
    ]

    command_update = FakeUpdate("/tasks")
    asyncio.run(tasks(command_update, FakeContext(RecordingOrchestrator(records=records))))
    assert_readable_task_list_payload(command_update.message.replies[-1], "TASK-0002", "улучшить список задач")

    for label in (TASKS_BUTTON, LEGACY_TASKS_BUTTON, "🗂 Последние", "🗂 Recent tasks"):
        update = FakeUpdate(label)
        orchestrator = RecordingOrchestrator(records=records)
        asyncio.run(handle_text(update, FakeContext(orchestrator)))

        assert orchestrator.created_texts == []
        assert len(update.message.replies) == 1
        assert_readable_task_list_payload(update.message.replies[-1], "TASK-0002", "улучшить список задач")

    task_card_keyboard = build_task_action_keyboard(records[0])
    assert "tasks:recent" in button_data(task_card_keyboard)

    for callback_data in ("tasks:recent", "tasks:list", "tasks:show"):
        update = FakeCallbackUpdate(callback_data)
        asyncio.run(handle_callback(update, make_records_callback_context(records)))

        assert_readable_task_list_payload(update.callback_query.edits[-1], "TASK-0002", "улучшить список задач")


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
    assert "🔍 Diff" in button_text(markup)
    assert "✅ Коммит" in button_text(markup)


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
        lambda task: PostRunActionResult(True, "Локальный commit создан.", branch_name="agent/TASK-0013-post-run"),
    )
    update = FakeCallbackUpdate("task:confirm_commit:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    assert "Локальный commit создан." in update.callback_query.edits[-1]["text"]
    assert "📤 Push" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_recent_tasks_message_with_tasks(tmp_path):
    first = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot улучши генерацию prompt и список задач")
    second = make_task_with_input(tmp_path, "TASK-0001", "pdlc-bot добавить кнопки")

    message = build_recent_tasks_message([first, second])
    markup = build_recent_tasks_keyboard([first, second])

    assert message == "🗂 Последние задачи\n\nОткрой задачу кнопкой ниже."
    assert "⚪ TASK-0002 — улучши генерацию prompt и список задач" in button_text(markup)
    assert "⚪ TASK-0001 — добавить кнопки" in button_text(markup)


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
    markup = build_recent_tasks_keyboard([record])

    assert button_text(markup) == ["⚪ TASK-0002", "🏠 Меню"]


def test_recent_tasks_message_truncates_long_title(tmp_path):
    record = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot " + "очень " * 30)

    markup = build_recent_tasks_keyboard([record])

    assert "…" in button_text(markup)[0]
    assert len(button_text(markup)[0]) < len("⚪ TASK-0002 — " + "очень " * 30)


def test_task_button_label_includes_short_title_or_falls_back_to_id(tmp_path):
    titled = make_task_with_input(tmp_path, "TASK-0025", "В pdlc-bot UX списка задач")
    missing_input_workspace = tmp_path / "TASK-0024"
    missing_input_workspace.mkdir()
    missing = TaskRecord(
        "TASK-0024",
        "pdlc-bot",
        "prompt_ready",
        str(missing_input_workspace),
        "2026-05-30T00:00:00+00:00",
    )

    assert build_task_button_label(titled) == "⚪ TASK-0025 — UX списка задач"
    assert build_task_button_label(missing) == "⚪ TASK-0024"


def test_recent_tasks_message_limits_to_ten_and_mentions_archive(tmp_path):
    records = [
        make_task_with_input(tmp_path, f"TASK-{index:04d}", f"В pdlc-bot задача {index}")
        for index in range(12, 0, -1)
    ]

    message = build_recent_tasks_message(records)
    markup = build_recent_tasks_keyboard(records)

    assert "TASK-0012" not in message
    assert "TASK-0003" not in message
    assert "TASK-0002" not in message
    assert "Более старые задачи доступны в архиве." in message
    assert "📦 Архив" in button_text(markup)
    assert "tasks:archive" in button_data(markup)
    assert "⚪ TASK-0012 — задача 12" in button_text(markup)
    assert "⚪ TASK-0003 — задача 3" in button_text(markup)
    assert len([text for text in button_text(markup) if text.startswith("⚪ TASK-")]) == 10


def test_archived_tasks_message_and_keyboard_show_older_tasks(tmp_path):
    records = [
        make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot старая задача"),
        make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot самая старая задача"),
    ]

    message = build_archived_tasks_message(records)
    markup = build_archived_tasks_keyboard(records)

    assert message == "📦 Архив задач\n\nОткрой задачу кнопкой ниже."
    assert "⚪ TASK-0002 — старая задача" in button_text(markup)
    assert "⚪ TASK-0001 — самая старая задача" in button_text(markup)
    assert "🗂 Последние" in button_text(markup)
    assert "⬅️ Назад" in button_text(markup)
    assert "🏠 Меню" in button_text(markup)


def test_callback_data_is_compact_and_contains_expected_ids():
    markup = build_task_actions_keyboard("TASK-0002")

    data = button_data(markup)
    assert "task:run_codex:TASK-0002" in data
    assert "task:details:TASK-0002" in data
    assert "task:prompt:TASK-0002" in data
    assert "task:artifacts:TASK-0002" in data
    assert "tasks:recent" in data
    assert "menu:show" in data
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


def test_task_actions_keyboard_contains_expected_buttons():
    markup = build_task_actions_keyboard("TASK-0002")

    texts = button_text(markup)
    assert "▶️ Запустить Codex" in texts
    assert "📄 Детали" in texts
    assert "🧠 Codex prompt" in texts
    assert "🛠 Детали" in texts
    assert "🗂 Последние" in texts
    assert "⬅️ Назад" in texts
    assert "🏠 Меню" in texts


def test_codex_post_run_keyboard_contains_safe_first_layer_actions():
    markup = build_codex_post_run_keyboard("TASK-0013")

    texts = button_text(markup)
    data = button_data(markup)
    assert "🔍 Diff" in texts
    assert "🧪 Тесты" in texts
    assert "📝 Review" in texts
    assert "✅ Коммит" in texts
    assert "🧹 Откат" in texts
    assert "task:show_diff:TASK-0013" in data
    assert "task:tests_again:TASK-0013" in data
    assert "task:review:TASK-0013" in data
    assert "task:commit:TASK-0013" in data
    assert "task:discard:TASK-0013" in data
    assert "task:artifacts:TASK-0013" in data
    assert "tasks:recent" in data
    assert "menu:show" in data
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


def test_changes_requested_keyboard_contains_review_and_fix_actions():
    markup = build_codex_changes_requested_keyboard("TASK-0013")

    texts = button_text(markup)
    data = button_data(markup)
    assert "📄 Review report" in texts
    assert "🔁 Доработать" in texts
    assert "🔍 Diff" in texts
    assert "🧹 Откат" in texts
    assert "task:review:TASK-0013" in data
    assert "task:fix:TASK-0013" in data
    assert all(len(item.encode("utf-8")) <= 64 for item in data)


def test_fix_prompt_ready_keyboard_contains_run_fix_button():
    markup = build_fix_prompt_ready_keyboard("TASK-0013")

    assert button_text(markup) == ["▶️ Запустить доработку", "📄 Детали", "🗂 Последние", "🏠 Меню"]
    assert button_data(markup) == ["task:run_fix:TASK-0013", "task:details:TASK-0013", "tasks:recent", "menu:show"]
    assert all(len(item.encode("utf-8")) <= 64 for item in button_data(markup))


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
    assert "🔍 Diff" not in texts


def test_task_action_keyboard_after_codex_run_shows_post_run_controls(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")

    markup = build_task_action_keyboard(record)
    texts = button_text(markup)

    assert task_result_state(record) == TASK_RESULT_READY_FOR_POST_RUN_ACTIONS
    assert "🔍 Diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_task_action_keyboard_committed_shows_push_branch(tmp_path):
    record = TaskRecord("TASK-0013", "pdlc-bot", "committed", str(tmp_path / "TASK-0013"), "2026-05-30T00:00:00+00:00")

    markup = build_task_action_keyboard(record)

    assert task_result_state(record) == TASK_RESULT_COMMITTED
    assert button_text(markup) == ["📤 Push", "🛠 Детали", "⬅️ Назад", "🗂 Последние", "🏠 Меню"]


def test_show_diff_callback_keeps_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:show_diff:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    assert "Diff для TASK-0013" in update.callback_query.edits[-1]["text"]
    assert "🔍 Diff" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_run_tests_again_callback_keeps_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:tests_again:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    assert "Повторный запуск тестов пока не реализован." in update.callback_query.edits[-1]["text"]
    assert "🔍 Diff" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_review_callback_creates_and_shows_review_report(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:review:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    text = update.callback_query.edits[-1]["text"]
    assert "Review report: TASK-0013" in text
    assert "Status: approved" in text
    assert (workspace / "review_report.md").exists()
    assert "📝 Review" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_fix_callback_shows_command_format(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:fix:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    assert "/fix TASK-0013 <замечания>" in update.callback_query.edits[-1]["text"]
    assert "fix_prompt.md" in update.callback_query.edits[-1]["text"]
    assert "📝 Review" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_run_fix_callback_is_placeholder(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    update = FakeCallbackUpdate("task:run_fix:TASK-0013")

    asyncio.run(handle_callback(update, FakeContext()))

    assert "ещё не реализован" in update.callback_query.edits[-1]["text"]
    assert "▶️ Запустить доработку" in button_text(update.callback_query.edits[-1]["reply_markup"])


def test_fix_command_without_task_id_shows_usage(monkeypatch):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    update = FakeUpdate("/fix")

    asyncio.run(fix(update, SimpleNamespace(args=[], application=SimpleNamespace(bot_data={"orchestrator": object()}))))

    assert update.message.replies[-1]["text"] == "Использование: /fix TASK-0001 <замечания>"


def test_fix_command_missing_task_shows_not_found(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    record = make_task_with_input(tmp_path, "TASK-0013", "В pdlc-bot тест")
    update = FakeUpdate("/fix TASK-9999 поправь")

    asyncio.run(fix(update, make_callback_context(record, args=["TASK-9999", "поправь"])))

    assert update.message.replies[-1]["text"] == "Задача TASK-9999 не найдена."


def test_fix_command_creates_review_comments_and_fix_prompt(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeUpdate("/fix TASK-0013 сократи кнопку")

    asyncio.run(fix(update, make_callback_context(record, args=["TASK-0013", "сократи", "кнопку"])))

    assert update.message.replies[-1]["text"].startswith("Fix prompt prepared.")
    assert (workspace / "review_comments.md").read_text(encoding="utf-8") == "сократи кнопку\n"
    fix_prompt = (workspace / "fix_prompt.md").read_text(encoding="utf-8")
    assert "сократи кнопку" in fix_prompt
    assert "Continue on existing agent branch" in fix_prompt
    assert "Do not commit, push, or deploy." in fix_prompt
    assert "▶️ Запустить доработку" in button_text(update.message.replies[-1]["reply_markup"])


def test_task_details_after_codex_run_shows_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:details:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    texts = button_text(update.callback_query.edits[-1]["reply_markup"])
    assert "🔍 Diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_task_details_changes_requested_shows_fix_button(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    write_changes_requested_review_report(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeCallbackUpdate("task:details:TASK-0013")

    asyncio.run(handle_callback(update, make_callback_context(record)))

    texts = button_text(update.callback_query.edits[-1]["reply_markup"])
    assert "📄 Review report" in texts
    assert "🔁 Доработать" in texts
    assert "✅ Коммит" not in texts


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
    assert "🛠 Детали TASK-0018" in text
    assert "- input.md" in text
    assert "- codex_prompt.md" in text
    assert button_text(update.callback_query.edits[-1]["reply_markup"]) == ["⬅️ Назад", "🗂 Последние", "🏠 Меню"]


def test_task_subview_keyboard_returns_to_task_list_and_menu():
    markup = build_task_subview_keyboard("TASK-0018")

    assert button_text(markup) == ["⬅️ Назад", "🗂 Последние", "🏠 Меню"]
    assert button_data(markup) == ["task:details:TASK-0018", "tasks:recent", "menu:show"]


def test_archive_callback_shows_older_tasks(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [
        make_task_with_input(tmp_path, f"TASK-{index:04d}", f"В pdlc-bot задача {index}")
        for index in range(12, 0, -1)
    ]
    update = FakeCallbackUpdate("tasks:archive")

    asyncio.run(handle_callback(update, make_records_callback_context(records)))

    text = update.callback_query.edits[-1]["text"]
    markup = update.callback_query.edits[-1]["reply_markup"]
    assert text == "📦 Архив задач\n\nОткрой задачу кнопкой ниже."
    assert "задача 2" not in text
    assert "Статус:" not in text
    assert "TASK-0012" not in text
    assert "⚪ TASK-0002 — задача 2" in button_text(markup)
    assert "task:details:TASK-0002" in button_data(markup)
    assert all(len(item.encode("utf-8")) <= 64 for item in button_data(markup))


def test_recent_tasks_callback_sends_text_list_and_short_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    records = [
        make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot улучшить список задач"),
        make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot добавить кнопку"),
    ]
    update = FakeCallbackUpdate("tasks:recent")

    asyncio.run(handle_callback(update, make_records_callback_context(records)))

    edit = update.callback_query.edits[-1]
    assert "Действия с задачами:" not in edit["text"]
    assert "улучшить список задач" not in edit["text"]
    assert "Статус:" not in edit["text"]
    assert button_text(edit["reply_markup"]) == [
        "⚪ TASK-0002 — улучшить список задач",
        "⚪ TASK-0001 — добавить кнопку",
        "🏠 Меню",
    ]


def test_task_command_after_codex_run_shows_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeUpdate("/task TASK-0013")

    asyncio.run(task(update, make_callback_context(record, args=["TASK-0013"])))

    texts = button_text(update.message.replies[-1]["reply_markup"])
    assert "🔍 Diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_prompt_after_codex_run_shows_post_run_buttons(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    update = FakeUpdate("/prompt TASK-0013")

    asyncio.run(prompt(update, make_callback_context(record, args=["TASK-0013"])))

    texts = button_text(update.message.replies[-1]["reply_markup"])
    assert "🔍 Diff" in texts
    assert "▶️ Запустить Codex" not in texts


def test_task_action_keyboard_running_shows_running_state(tmp_path):
    record = TaskRecord("TASK-0015", "pdlc-bot", "codex_running", str(tmp_path / "TASK-0015"), "2026-05-30T00:00:00+00:00")

    markup = build_task_action_keyboard(record)

    assert task_result_state(record) == "running"
    assert button_text(markup) == ["⏳ Выполняется", "🛠 Детали", "⬅️ Назад", "🗂 Последние", "🏠 Меню"]


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


def test_user_button_labels_are_short(tmp_path):
    workspace = tmp_path / "TASK-0013"
    write_successful_post_run_artifacts(workspace)
    task_record = TaskRecord("TASK-0013", "pdlc-bot", "prompt_ready", str(workspace), "2026-05-30T00:00:00+00:00")
    project = Project(name="pdlc-bot")
    markups = [
        build_main_menu_keyboard(),
        build_task_action_keyboard(make_task("TASK-0002")),
        build_task_action_keyboard(task_record),
        build_task_action_keyboard(TaskRecord("TASK-0014", "pdlc-bot", "committed", str(tmp_path / "TASK-0014"), "2026-05-30T00:00:00+00:00")),
        build_task_subview_keyboard("TASK-0013"),
        build_commit_confirm_keyboard("TASK-0013"),
        build_push_branch_keyboard("TASK-0013"),
        build_push_confirm_keyboard("TASK-0013"),
        build_discard_confirm_keyboard("TASK-0013"),
        build_recent_tasks_keyboard([make_task("TASK-0001")]),
        build_archived_tasks_keyboard([make_task("TASK-0001")]),
        build_project_details_keyboard(project),
        build_project_tasks_keyboard(project),
        build_add_project_stub_keyboard(),
    ]

    labels = [text for markup in markups if markup is not None for text in button_text(markup)]

    for long_label in LONG_BUTTON_LABELS:
        assert all(long_label not in label for label in labels)


def test_confirm_keyboards_separate_commit_push_and_discard():
    assert button_data(build_commit_confirm_keyboard("TASK-0013")) == [
        "task:confirm_commit:TASK-0013",
        "task:details:TASK-0013",
        "menu:show",
    ]
    assert button_data(build_push_branch_keyboard("TASK-0013")) == [
        "task:push:TASK-0013",
        "task:details:TASK-0013",
        "menu:show",
    ]
    assert button_data(build_push_confirm_keyboard("TASK-0013")) == [
        "task:confirm_push:TASK-0013",
        "task:details:TASK-0013",
        "menu:show",
    ]
    assert button_data(build_discard_confirm_keyboard("TASK-0013")) == [
        "task:confirm_discard:TASK-0013",
        "task:details:TASK-0013",
        "menu:show",
    ]


def test_recent_tasks_keyboard_contains_task_buttons(tmp_path):
    first = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot улучшить список задач")
    second = make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot добавить кнопки")
    markup = build_recent_tasks_keyboard([first, second])

    assert button_text(markup) == [
        "⚪ TASK-0002 — улучшить список задач",
        "⚪ TASK-0001 — добавить кнопки",
        "🏠 Меню",
    ]
    assert button_data(markup) == ["task:details:TASK-0002", "task:details:TASK-0001", "menu:show"]


def test_project_keyboard_contains_projects():
    projects = [
        Project(name="pdlc-bot", aliases=["pdlc"]),
        Project(name="example-api", aliases=["api"]),
    ]

    markup = build_project_keyboard(projects)

    assert "📁 pdlc-bot" in button_text(markup)
    assert "📁 example-api" in button_text(markup)
    assert "➕ Добавить проект" in button_text(markup)
    assert "project:show:pdlc-bot" in button_data(markup)
    assert "project:show:example-api" in button_data(markup)
    assert "projects:add" in button_data(markup)
    assert all(len(item.encode("utf-8")) <= 64 for item in button_data(markup))


def test_project_keyboard_contains_add_stub_without_projects():
    markup = build_project_keyboard([])

    assert "➕ Добавить проект" in button_text(markup)
    assert "projects:add" in button_data(markup)


def test_projects_message_shows_project_cards_with_counts(tmp_path):
    project = Project(
        name="pdlc-bot",
        description="Telegram PDLC бот",
        repo_url="https://github.com/drthalas/pdlc-bot.git",
        local_path=str(tmp_path),
    )
    task = make_task_with_input(tmp_path, "TASK-0001", "В pdlc-bot улучшить проекты")

    message = build_projects_message([project], [task])

    assert "📋 Проекты:" in message
    assert "• pdlc-bot" in message
    assert "Описание: Telegram PDLC бот" in message
    assert "GitHub URL: https://github.com/drthalas/pdlc-bot.git" in message
    assert "Статус: локальная папка доступна" in message
    assert "Задач: 1" in message


def test_project_details_message(tmp_path):
    project = Project(
        name="pdlc-bot",
        description="Telegram PDLC бот",
        aliases=["pdlc", "бот задач"],
        repo_url="https://github.com/drthalas/pdlc-bot.git",
        local_path=str(tmp_path),
        stack=["Python", "Telegram Bot", "SQLite"],
    )
    task = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot добавь карточку проекта")

    message = build_project_details_message(project, [task])

    assert "📁 Карточка проекта: pdlc-bot" in message
    assert "Описание: Telegram PDLC бот" in message
    assert "GitHub URL: https://github.com/drthalas/pdlc-bot.git" in message
    assert f"Local path: {tmp_path}" in message
    assert "Статус: локальная папка доступна" in message
    assert "Алиасы: pdlc, бот задач" in message
    assert "Стек: Python, Telegram Bot, SQLite" in message
    assert "Задач: 1" in message
    assert "Задачи проекта открываются кнопкой ниже." in message
    assert "TASK-0002 — добавь карточку проекта" not in message


def test_project_details_keyboard_contains_expected_actions():
    project = Project(name="pdlc-bot")
    markup = build_project_details_keyboard(project)

    assert "🗂 Задачи проекта" in button_text(markup)
    assert "⬅️ Назад к проектам" in button_text(markup)
    assert "➕ Добавить проект" in button_text(markup)
    assert "🏠 Меню" in button_text(markup)
    assert button_data(markup) == ["project:tasks:pdlc-bot", "projects:show", "projects:add", "menu:show"]
    assert all(len(item.encode("utf-8")) <= 64 for item in button_data(markup))


def test_project_tasks_message_filters_by_project(tmp_path):
    pdlc_task = make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot добавить GitHub URL", "pdlc-bot")
    other_task = make_task_with_input(tmp_path, "TASK-0001", "В other изменить API", "other")

    message = build_project_tasks_message(Project(name="pdlc-bot"), [pdlc_task, other_task])

    assert "🗂 Задачи проекта pdlc-bot" in message
    assert "Открой задачу кнопкой ниже." in message
    assert "добавить GitHub URL" not in message
    assert "TASK-0001" not in message
    assert button_data(build_project_tasks_keyboard(Project(name="pdlc-bot"))) == [
        "project:show:pdlc-bot",
        "projects:show",
        "menu:show",
    ]
    assert button_data(build_project_task_buttons(Project(name="pdlc-bot"), [pdlc_task, other_task])) == [
        "task:details:TASK-0002",
        "project:show:pdlc-bot",
        "projects:show",
        "menu:show",
    ]
    assert "⚪ TASK-0002 — добавить GitHub URL" in button_text(
        build_project_task_buttons(Project(name="pdlc-bot"), [pdlc_task, other_task])
    )


def test_add_project_stub_is_safe():
    message = build_add_project_stub_message()
    markup = build_add_project_stub_keyboard()

    assert "Добавление проекта пока не реализовано." in message
    assert "ничего не клонирует" in message
    assert "не меняет config/projects.yaml" in message
    assert button_data(markup) == ["projects:show", "menu:show"]


def test_project_callbacks_show_card_tasks_and_safe_add_stub(monkeypatch, tmp_path):
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    project = Project(
        name="pdlc-bot",
        description="Telegram PDLC бот",
        repo_url="https://github.com/drthalas/pdlc-bot.git",
        local_path=str(tmp_path),
    )
    records = [make_task_with_input(tmp_path, "TASK-0002", "В pdlc-bot добавить проекты")]

    show_update = FakeCallbackUpdate("project:show:pdlc-bot")
    asyncio.run(handle_callback(show_update, make_project_callback_context([project], records)))
    assert "📁 Карточка проекта: pdlc-bot" in show_update.callback_query.edits[-1]["text"]
    assert "🗂 Задачи проекта" in button_text(show_update.callback_query.edits[-1]["reply_markup"])

    tasks_update = FakeCallbackUpdate("project:tasks:pdlc-bot")
    asyncio.run(handle_callback(tasks_update, make_project_callback_context([project], records)))
    assert "🗂 Задачи проекта pdlc-bot" in tasks_update.callback_query.edits[-1]["text"]
    assert "⚪ TASK-0002 — добавить проекты" in button_text(tasks_update.callback_query.edits[-1]["reply_markup"])

    add_update = FakeCallbackUpdate("projects:add")
    asyncio.run(handle_callback(add_update, make_project_callback_context([project], records)))
    assert "ничего не клонирует" in add_update.callback_query.edits[-1]["text"]
