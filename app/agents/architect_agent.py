from __future__ import annotations

from app.agents.intake_agent import IntakeResult


class ArchitectAgent:
    def create_plan(self, intake: IntakeResult) -> str:
        context_files = intake.project.context_files if intake.project else []
        test_commands = intake.project.test_commands if intake.project else []

        context_block = "\n".join(f"- {path}" for path in context_files) or "- Not configured"
        test_block = "\n".join(f"- `{command}`" for command in test_commands) or "- Not configured"

        return f"""# Implementation Plan

## Recommended Context
{context_block}

## Plan
1. Inspect the relevant project files and existing patterns.
2. Identify the smallest safe change that satisfies the request.
3. Implement the change in the target repository.
4. Run focused verification.
5. Summarize changed files, behavior, and remaining risks.

## Acceptance Criteria
- The requested behavior is implemented or the blocker is clearly documented.
- Existing project conventions are followed.
- Relevant tests or checks pass, or skipped checks are explained.
- No unrelated files are changed.

## Suggested Verification
{test_block}

## Risk Level
{intake.project.risk_level if intake.project else "unknown"}
"""
