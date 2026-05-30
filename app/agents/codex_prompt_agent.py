from __future__ import annotations

from app.agents.intake_agent import IntakeResult


BASE_CONTEXT_FILES = [
    "PROJECT_CONTEXT.md",
    "TASKS.md",
    "DECISIONS.md",
    "README.md",
    "docs/ROADMAP.md",
    "docs/CODEX_RUNNER_V0.md",
]

MAC_MINI_CONTEXT_FILE = "docs/MAC_MINI_RUNBOOK.md"
MAC_MINI_KEYWORDS = (
    "mac mini",
    "deployment",
    "deploy",
    "runbook",
    "launchd",
    "service",
    "runtime",
)

PROJECT_RULES = [
    "User-facing Telegram text should be Russian by default.",
    "Technical artifact filenames, internal status values, and code identifiers may remain English.",
    "Codex Runner must not commit, push, or deploy without explicit approval.",
    "Mac mini is the execution runtime.",
    "Railway dashboard / PDLC Control Center is planned later.",
    "Tester/QA Agent is mandatory in the future roadmap.",
    "Before changing files, keep scope minimal and do not touch unrelated files.",
]


def context_files_for_request(raw_request: str) -> list[str]:
    lowered = raw_request.lower()
    files = list(BASE_CONTEXT_FILES)
    if any(keyword in lowered for keyword in MAC_MINI_KEYWORDS):
        files.append(MAC_MINI_CONTEXT_FILE)
    files.append("Relevant docs/*.md files for the task topic")
    return files


class CodexPromptAgent:
    def create_prompt(self, task_id: str, intake: IntakeResult, brief: str, plan: str) -> str:
        project = intake.project
        project_name = project.name if project else "UNKNOWN_PROJECT"
        local_path = project.local_path if project else "UNKNOWN_LOCAL_PATH"
        repo_url = project.repo_url if project else "UNKNOWN_REPO_URL"
        context_files = "\n".join(f"- {file}" for file in context_files_for_request(intake.raw_request))
        project_rules = "\n".join(f"- {rule}" for rule in PROJECT_RULES)

        return f"""You are Codex working on task {task_id}.

Target project: {project_name}
Repository URL: {repo_url}
Local path: {local_path}

User request:
{intake.raw_request}

Before editing, read these project memory/context files when present:
{context_files}

Permanent project rules:
{project_rules}

Use the following brief and plan as guidance. Read the target repository before editing, keep changes scoped, and verify your work.

{brief}

{plan}
"""
