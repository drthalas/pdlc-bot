from __future__ import annotations

from app.agents.intake_agent import IntakeResult


class CodexPromptAgent:
    def create_prompt(self, task_id: str, intake: IntakeResult, brief: str, plan: str) -> str:
        project = intake.project
        project_name = project.name if project else "UNKNOWN_PROJECT"
        local_path = project.local_path if project else "UNKNOWN_LOCAL_PATH"
        repo_url = project.repo_url if project else "UNKNOWN_REPO_URL"

        return f"""You are Codex working on task {task_id}.

Target project: {project_name}
Repository URL: {repo_url}
Local path: {local_path}

User request:
{intake.raw_request}

Use the following brief and plan as guidance. Read the target repository before editing, keep changes scoped, and verify your work.

{brief}

{plan}
"""
