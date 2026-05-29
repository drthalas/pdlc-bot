from app.task_workspace import list_artifacts


def test_list_artifacts_returns_files(tmp_path):
    workspace = tmp_path / "TASK-0001"
    workspace.mkdir()
    (workspace / "codex_prompt.md").write_text("prompt", encoding="utf-8")
    (workspace / "input.md").write_text("input", encoding="utf-8")
    (workspace / "nested").mkdir()

    assert list_artifacts(workspace) == ["codex_prompt.md", "input.md"]


def test_list_artifacts_returns_empty_for_missing_workspace(tmp_path):
    assert list_artifacts(tmp_path / "missing") == []
