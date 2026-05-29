from app.orchestrator import Orchestrator
from app.project_registry import ProjectRegistry
from app.task_store import TaskStore
from app.task_workspace import TaskWorkspace


def build_orchestrator(tmp_path):
    config_path = tmp_path / "projects.yaml"
    config_path.write_text(
        """
projects:
  - name: ai-sales-assistant
    aliases:
      - sales bot
    repo_url: https://example.com/ai-sales-assistant.git
    local_path: /tmp/ai-sales-assistant
    stack:
      - Python
    context_files:
      - README.md
    test_commands:
      - pytest
    risk_level: medium
""",
        encoding="utf-8",
    )
    return Orchestrator(
        registry=ProjectRegistry(config_path),
        store=TaskStore(tmp_path / "tasks.sqlite3"),
        workspace=TaskWorkspace(tmp_path / "tasks"),
    )


def test_creates_task_with_detected_project(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout in sales bot")

    assert result.project_detected is True
    assert result.record.project_name == "ai-sales-assistant"
    assert result.record.status == "prompt_ready"
    assert "Project: ai-sales-assistant" in result.response_text


def test_creates_task_without_detected_project(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout")

    assert result.project_detected is False
    assert result.record.project_name is None
    assert "Project: not detected. Please mention a project name or alias from /projects." in result.response_text


def test_creates_artifacts(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout in ai sales assistant")
    task_path = tmp_path / "tasks" / result.record.task_id

    assert (task_path / "input.md").exists()
    assert (task_path / "project.json").exists()
    assert (task_path / "analysis.md").exists()
    assert (task_path / "implementation_plan.md").exists()
    assert (task_path / "codex_prompt.md").exists()
