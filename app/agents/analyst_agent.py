from __future__ import annotations

from app.agents.intake_agent import IntakeResult


class AnalystAgent:
    def create_brief(self, intake: IntakeResult) -> str:
        project_name = intake.project.name if intake.project else "Unknown"
        project_stack = ", ".join(intake.project.stack) if intake.project and intake.project.stack else "Unknown"

        return f"""# Task Brief

## Request
{intake.raw_request}

## Detected Project
{project_name}

## Detected Task Type
{intake.task_type}

## Project Stack
{project_stack}

## Notes
- Confirm the target project if detection is wrong or missing.
- Keep the first implementation pass small and easy to review.
- Do not perform destructive actions without explicit user approval.
"""
