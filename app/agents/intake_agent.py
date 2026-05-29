from __future__ import annotations

from dataclasses import dataclass

from app.project_registry import Project, ProjectRegistry


@dataclass(frozen=True)
class IntakeResult:
    raw_request: str
    project: Project | None
    task_type: str


class IntakeAgent:
    def __init__(self, registry: ProjectRegistry) -> None:
        self.registry = registry

    def analyze(self, text: str) -> IntakeResult:
        return IntakeResult(
            raw_request=text.strip(),
            project=self.registry.find_in_text(text),
            task_type=self._detect_task_type(text),
        )

    def _detect_task_type(self, text: str) -> str:
        lowered = text.lower()
        if any(word in lowered for word in ("bug", "fix", "error", "broken", "traceback")):
            return "bugfix"
        if any(word in lowered for word in ("refactor", "cleanup", "simplify")):
            return "refactor"
        if any(word in lowered for word in ("test", "coverage", "pytest")):
            return "test"
        if any(word in lowered for word in ("docs", "readme", "documentation")):
            return "documentation"
        return "feature"
