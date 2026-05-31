import pytest

from app.task_store import TaskStore


def test_creates_task(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")

    record = store.reserve_task("example-api", str(tmp_path / "PENDING"))

    assert record.task_id == "TASK-0001"
    assert record.project_name == "example-api"
    assert record.status == "created"
    assert record.workspace_path.endswith("TASK-0001")


def test_get_task_by_task_id(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    created = store.reserve_task("example-api", str(tmp_path / "PENDING"))

    record = store.get_task(created.task_id)

    assert record == created
    assert store.get_task("TASK-9999") is None


def test_update_status(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    created = store.reserve_task("example-api", str(tmp_path / "PENDING"))

    assert store.update_status(created.task_id, "prompt_ready") is True
    assert store.get_task(created.task_id).status == "prompt_ready"
    assert store.update_status("TASK-9999", "failed") is False


def test_invalid_status_rejected(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    created = store.reserve_task("example-api", str(tmp_path / "PENDING"))

    with pytest.raises(ValueError, match="Invalid task status"):
        store.update_status(created.task_id, "done")


def test_list_tasks_returns_newest_first_and_respects_limit(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    first = store.reserve_task("first-project", str(tmp_path / "PENDING"))
    second = store.reserve_task("second-project", str(tmp_path / "PENDING"))
    third = store.reserve_task("third-project", str(tmp_path / "PENDING"))

    records = store.list_tasks(limit=2)

    assert [record.task_id for record in records] == [third.task_id, second.task_id]
    assert records[0].project_name == "third-project"
    assert first.task_id not in [record.task_id for record in records]


def test_list_tasks_supports_archive_offset(tmp_path):
    store = TaskStore(tmp_path / "tasks.sqlite3")
    first = store.reserve_task("first-project", str(tmp_path / "PENDING"))
    second = store.reserve_task("second-project", str(tmp_path / "PENDING"))
    third = store.reserve_task("third-project", str(tmp_path / "PENDING"))

    records = store.list_tasks(limit=2, offset=1)

    assert [record.task_id for record in records] == [second.task_id, first.task_id]
    assert third.task_id not in [record.task_id for record in records]
