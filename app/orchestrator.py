from __future__ import annotations

import os
from dataclasses import dataclass

from app.agents.analyst_agent import AnalystAgent
from app.agents.architect_agent import ArchitectAgent
from app.agents.codex_prompt_agent import CodexPromptAgent
from app.agents.intake_agent import IntakeAgent
from app.project_registry import ProjectRegistry
from app.task_store import TaskRecord, TaskStore
from app.task_workspace import TaskWorkspace


@dataclass(frozen=True)
class OrchestrationResult:
    record: TaskRecord
    project_detected: bool
    response_text: str


class Orchestrator:
    def __init__(
        self,
        registry: ProjectRegistry | None = None,
        store: TaskStore | None = None,
        workspace: TaskWorkspace | None = None,
    ) -> None:
        projects_config = os.getenv("PROJECTS_CONFIG_PATH", "config/projects.yaml")
        tasks_dir = os.getenv("TASKS_DIR", "tasks")
        database_path = os.getenv("DATABASE_PATH", "tasks/pdlc_bot.sqlite3")

        self.registry = registry or ProjectRegistry(projects_config)
        self.store = store or TaskStore(database_path)
        self.workspace = workspace or TaskWorkspace(tasks_dir)
        self.intake_agent = IntakeAgent(self.registry)
        self.analyst_agent = AnalystAgent()
        self.architect_agent = ArchitectAgent()
        self.codex_prompt_agent = CodexPromptAgent()

    def create_task(self, text: str) -> OrchestrationResult:
        intake = self.intake_agent.analyze(text)
        record = self.store.reserve_task(
            project_name=intake.project.name if intake.project else None,
            workspace_path_template=str(self.workspace.tasks_dir / "PENDING"),
        )
        task_path = self.workspace.create(record.task_id)

        brief = self.analyst_agent.create_brief(intake)
        self.store.update_status(record.task_id, "analyzed")
        plan = self.architect_agent.create_plan(intake)
        self.store.update_status(record.task_id, "planned")
        prompt = self.codex_prompt_agent.create_prompt(record.task_id, intake, brief, plan)

        self.workspace.write_text(record.task_id, "input.md", f"{intake.raw_request}\n")
        self.workspace.write_json(
            record.task_id,
            "project.json",
            intake.project.to_dict() if intake.project else {"project": None, "message": "No project detected"},
        )
        self.workspace.write_text(record.task_id, "analysis.md", brief)
        self.workspace.write_text(record.task_id, "implementation_plan.md", plan)
        self.workspace.write_text(record.task_id, "codex_prompt.md", prompt)
        self.store.update_status(record.task_id, "prompt_ready")

        response = self._response_text(record.task_id, task_path, intake.project.name if intake.project else None)
        stored_record = self.store.get_task(record.task_id) or record
        return OrchestrationResult(
            record=TaskRecord(
                task_id=stored_record.task_id,
                project_name=stored_record.project_name,
                status=stored_record.status,
                workspace_path=str(task_path),
                created_at=stored_record.created_at,
            ),
            project_detected=intake.project is not None,
            response_text=response,
        )

    def _response_text(self, task_id: str, task_path: object, project_name: str | None) -> str:
        project_line = (
            f"Project: {project_name}"
            if project_name
            else "Project: not detected. Please mention a project name or alias from /projects."
        )
        return (
            f"Created {task_id}\n"
            f"{project_line}\n"
            f"Workspace: {task_path}\n"
            "Artifacts: input.md, project.json, analysis.md, implementation_plan.md, codex_prompt.md"
        )
