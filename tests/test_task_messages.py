from app.task_messages import (
    build_prompt_response,
    format_task_artifacts_response,
    format_task_created_response,
    format_task_details_response,
    task_title,
)
from app.task_store import TaskRecord, TaskStore


def make_record(tmp_path, project_name="ai-sales-assistant"):
    return TaskRecord(
        task_id="TASK-0001",
        project_name=project_name,
        status="prompt_ready",
        workspace_path=str(tmp_path / "TASK-0001"),
        created_at="2026-05-30T00:00:00+00:00",
    )


def test_format_created_response_with_project(tmp_path):
    record = make_record(tmp_path)

    message = format_task_created_response(
        record,
        project_detected=True,
        artifacts=["input.md", "codex_prompt.md"],
    )

    assert message.startswith("✅ Задача создана: TASK-0001")
    assert "Проект: ai-sales-assistant" in message
    assert "Статус: ⚪ prompt готов" in message
    assert "Текущий этап:" in message
    assert "Прогресс:" in message
    assert "✅ задача создана" in message
    assert "Технические файлы скрыты в отдельной кнопке." in message
    assert "- input.md" not in message


def test_format_created_response_without_project(tmp_path):
    record = make_record(tmp_path, project_name=None)

    message = format_task_created_response(record, project_detected=False, artifacts=["input.md"])

    assert message.startswith("⚠️ Задача создана: TASK-0001")
    assert "Проект: не определён" in message
    assert "В следующий раз укажи название проекта или alias из /projects." in message
    assert "Файлы:" not in message


def test_task_title_uses_first_input_line_and_strips_project_prefix(tmp_path):
    record = make_record(tmp_path, project_name="pdlc-bot")
    workspace = tmp_path / "TASK-0001"
    workspace.mkdir()
    (workspace / "input.md").write_text("\nВ pdlc-bot улучши генерацию prompt и список задач\n", encoding="utf-8")

    assert task_title(record) == "улучши генерацию prompt и список задач"


def test_task_title_truncates_long_input(tmp_path):
    record = make_record(tmp_path, project_name="pdlc-bot")
    workspace = tmp_path / "TASK-0001"
    workspace.mkdir()
    (workspace / "input.md").write_text("В pdlc-bot " + "очень " * 30, encoding="utf-8")

    title = task_title(record, limit=40)

    assert len(title) <= 40
    assert title.endswith("…")


def test_task_title_missing_input_falls_back_to_task_id(tmp_path):
    record = make_record(tmp_path, project_name="pdlc-bot")

    assert task_title(record) == "TASK-0001"


def test_task_details_include_task_title(tmp_path):
    record = make_record(tmp_path, project_name="pdlc-bot")
    workspace = tmp_path / "TASK-0001"
    workspace.mkdir()
    (workspace / "input.md").write_text("pdlc-bot: улучшить список задач\n", encoding="utf-8")

    message = format_task_details_response(record, artifacts=["input.md"])

    assert "Название: улучшить список задач" in message
    assert "Текущий этап:" in message
    assert "Прогресс:" in message
    assert "input.md" not in message


def test_task_artifacts_response_shows_files_separately(tmp_path):
    record = make_record(tmp_path, project_name="pdlc-bot")

    message = format_task_artifacts_response(record, artifacts=["input.md", "codex_prompt.md"])

    assert message.startswith("🛠 Детали TASK-0001")
    assert "Рабочая папка:" in message
    assert "- input.md" in message
    assert "- codex_prompt.md" in message


def test_build_prompt_response_returns_prompt(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    record = store.reserve_task("ai-sales-assistant", str(tmp_path / "PENDING"))
    workspace = tmp_path / record.task_id
    workspace.mkdir()
    (workspace / "codex_prompt.md").write_text("Use Codex carefully.", encoding="utf-8")

    response = build_prompt_response(store, record.task_id)

    assert response.found is True
    assert response.message == "Use Codex carefully."


def test_build_prompt_response_handles_missing_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")

    response = build_prompt_response(store, "TASK-9999")

    assert response.found is False
    assert response.message == "Задача TASK-9999 не найдена."


def test_build_prompt_response_handles_missing_prompt_file(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    record = store.reserve_task("ai-sales-assistant", str(tmp_path / "PENDING"))
    (tmp_path / record.task_id).mkdir()

    response = build_prompt_response(store, record.task_id)

    assert response.found is False
    assert response.message == "Codex prompt для TASK-0001 не найден."


def test_build_prompt_response_truncates_long_prompt(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    record = store.reserve_task("ai-sales-assistant", str(tmp_path / "PENDING"))
    workspace = tmp_path / record.task_id
    workspace.mkdir()
    (workspace / "codex_prompt.md").write_text("abcdef", encoding="utf-8")

    response = build_prompt_response(store, record.task_id, preview_limit=3)

    assert response.found is True
    assert response.message.startswith("abc")
    assert "Prompt обрезан" in response.message
    assert str(workspace / "codex_prompt.md") in response.message
