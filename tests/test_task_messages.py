from app.task_messages import build_prompt_response, format_task_created_response
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

    assert message.startswith("✅ Task created: TASK-0001")
    assert "Project: ai-sales-assistant" in message
    assert "Status: prompt_ready" in message
    assert "- input.md" in message
    assert "- /task TASK-0001 — show task details" in message
    assert "- /prompt TASK-0001 — show Codex prompt" in message


def test_format_created_response_without_project(tmp_path):
    record = make_record(tmp_path, project_name=None)

    message = format_task_created_response(record, project_detected=False, artifacts=["input.md"])

    assert message.startswith("⚠️ Task created: TASK-0001")
    assert "Project: not detected" in message
    assert "Please mention a project name or alias from /projects next time." in message
    assert "Artifacts:" not in message


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
    assert response.message == "Task TASK-9999 not found."


def test_build_prompt_response_handles_missing_prompt_file(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    record = store.reserve_task("ai-sales-assistant", str(tmp_path / "PENDING"))
    (tmp_path / record.task_id).mkdir()

    response = build_prompt_response(store, record.task_id)

    assert response.found is False
    assert response.message == "Codex prompt not found for TASK-0001."


def test_build_prompt_response_truncates_long_prompt(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    record = store.reserve_task("ai-sales-assistant", str(tmp_path / "PENDING"))
    workspace = tmp_path / record.task_id
    workspace.mkdir()
    (workspace / "codex_prompt.md").write_text("abcdef", encoding="utf-8")

    response = build_prompt_response(store, record.task_id, preview_limit=3)

    assert response.found is True
    assert response.message.startswith("abc")
    assert "Prompt truncated" in response.message
    assert str(workspace / "codex_prompt.md") in response.message
