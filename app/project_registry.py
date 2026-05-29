from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class Project:
    name: str
    aliases: list[str] = field(default_factory=list)
    repo_url: str = ""
    local_path: str = ""
    stack: list[str] = field(default_factory=list)
    context_files: list[str] = field(default_factory=list)
    test_commands: list[str] = field(default_factory=list)
    risk_level: str = "medium"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProjectRegistry:
    def __init__(self, config_path: str | Path = "config/projects.yaml") -> None:
        self.config_path = Path(config_path)
        self._projects: dict[str, Project] = {}
        self._alias_index: dict[str, str] = {}
        self.reload()

    def reload(self) -> None:
        self._projects = {}
        self._alias_index = {}

        if not self.config_path.exists():
            return

        with self.config_path.open("r", encoding="utf-8") as file:
            payload = yaml.safe_load(file) or {}

        for item in payload.get("projects", []):
            project = Project(
                name=str(item.get("name", "")).strip(),
                aliases=[str(alias).strip() for alias in item.get("aliases", [])],
                repo_url=str(item.get("repo_url", "")).strip(),
                local_path=str(item.get("local_path", "")).strip(),
                stack=[str(value).strip() for value in item.get("stack", [])],
                context_files=[str(value).strip() for value in item.get("context_files", [])],
                test_commands=[str(value).strip() for value in item.get("test_commands", [])],
                risk_level=str(item.get("risk_level", "medium")).strip() or "medium",
            )
            if not project.name:
                continue

            self._projects[project.name.lower()] = project
            self._alias_index[project.name.lower()] = project.name.lower()
            for alias in project.aliases:
                if alias:
                    self._alias_index[alias.lower()] = project.name.lower()

    def list_projects(self) -> list[Project]:
        return sorted(self._projects.values(), key=lambda project: project.name.lower())

    def get(self, name_or_alias: str) -> Project | None:
        key = self._alias_index.get(name_or_alias.strip().lower())
        if key is None:
            return None
        return self._projects.get(key)

    def find_in_text(self, text: str) -> Project | None:
        normalized = text.lower()
        candidates = sorted(self._alias_index, key=len, reverse=True)
        for candidate in candidates:
            if candidate and candidate in normalized:
                return self._projects[self._alias_index[candidate]]
        return None
