from __future__ import annotations

import json
from pathlib import Path
from typing import Any


class TaskWorkspace:
    def __init__(self, tasks_dir: str | Path = "tasks") -> None:
        self.tasks_dir = Path(tasks_dir)
        self.tasks_dir.mkdir(parents=True, exist_ok=True)

    def path_for(self, task_id: str) -> Path:
        return self.tasks_dir / task_id

    def create(self, task_id: str) -> Path:
        path = self.path_for(task_id)
        path.mkdir(parents=True, exist_ok=False)
        return path

    def write_text(self, task_id: str, filename: str, content: str) -> Path:
        path = self.path_for(task_id) / filename
        path.write_text(content, encoding="utf-8")
        return path

    def write_json(self, task_id: str, filename: str, payload: dict[str, Any]) -> Path:
        content = json.dumps(payload, indent=2, ensure_ascii=False)
        return self.write_text(task_id, filename, f"{content}\n")
