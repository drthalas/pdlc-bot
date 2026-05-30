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
    assert result.response_text.startswith("✅ Task created: TASK-0001")
    assert "Project: ai-sales-assistant" in result.response_text
    assert "Status: prompt_ready" in result.response_text
    assert "- codex_prompt.md" in result.response_text
    assert "- /prompt TASK-0001 — show Codex prompt" in result.response_text


def test_creates_task_without_detected_project(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout")

    assert result.project_detected is False
    assert result.record.project_name is None
    assert result.response_text.startswith("⚠️ Task created: TASK-0001")
    assert "Project: not detected" in result.response_text
    assert "Please mention a project name or alias from /projects next time." in result.response_text


def test_creates_artifacts(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout in ai sales assistant")
    task_path = tmp_path / "tasks" / result.record.task_id

    assert (task_path / "input.md").exists()
    assert (task_path / "project.json").exists()
    assert (task_path / "analysis.md").exists()
    assert (task_path / "implementation_plan.md").exists()
    assert (task_path / "codex_prompt.md").exists()


def test_codex_prompt_contains_project_context_files_and_rules(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant улучши Telegram UX")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    for filename in (
        "PROJECT_CONTEXT.md",
        "TASKS.md",
        "DECISIONS.md",
        "README.md",
        "docs/ROADMAP.md",
        "docs/CODEX_RUNNER_V0.md",
    ):
        assert filename in prompt
    assert "Relevant docs/*.md files for the task topic" in prompt
    assert "User-facing Telegram text should be Russian by default." in prompt
    assert "Technical artifact filenames, internal status values, and code identifiers may remain English." in prompt
    assert "Codex Runner must not commit, push, or deploy without explicit approval." in prompt
    assert "Mac mini is the execution runtime." in prompt
    assert "Railway dashboard / PDLC Control Center is planned later." in prompt
    assert "Tester/QA Agent is mandatory in the future roadmap." in prompt
    assert "keep scope minimal and do not touch unrelated files" in prompt


def test_codex_prompt_includes_mac_mini_runbook_for_deployment_tasks(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant обнови Mac mini deployment runbook")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    assert "docs/MAC_MINI_RUNBOOK.md" in prompt
