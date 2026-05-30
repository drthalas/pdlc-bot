from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


VALID_TASK_STATUSES = frozenset(
    {
        "created",
        "analyzed",
        "planned",
        "prompt_ready",
        "codex_running",
        "coding",
        "testing",
        "failed",
        "cancelled",
    }
)


@dataclass(frozen=True)
class TaskRecord:
    task_id: str
    project_name: str | None
    status: str
    workspace_path: str
    created_at: str


class TaskStore:
    def __init__(self, database_path: str | Path = "tasks/pdlc_bot.sqlite3") -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.database_path)

    def _init_db(self) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT UNIQUE NOT NULL,
                    project_name TEXT,
                    status TEXT NOT NULL,
                    workspace_path TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )

    def reserve_task(self, project_name: str | None, workspace_path_template: str) -> TaskRecord:
        created_at = datetime.now(timezone.utc).isoformat()
        with self._connect() as connection:
            cursor = connection.execute(
                "INSERT INTO tasks (task_id, project_name, status, workspace_path, created_at) VALUES (?, ?, ?, ?, ?)",
                ("PENDING", project_name, "created", workspace_path_template, created_at),
            )
            task_id = f"TASK-{cursor.lastrowid:04d}"
            workspace_path = workspace_path_template.replace("PENDING", task_id)
            connection.execute(
                "UPDATE tasks SET task_id = ?, workspace_path = ? WHERE id = ?",
                (task_id, workspace_path, cursor.lastrowid),
            )

        return TaskRecord(
            task_id=task_id,
            project_name=project_name,
            status="created",
            workspace_path=workspace_path,
            created_at=created_at,
        )

    def get_task(self, task_id: str) -> TaskRecord | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT task_id, project_name, status, workspace_path, created_at
                FROM tasks
                WHERE task_id = ?
                """,
                (task_id,),
            ).fetchone()

        if row is None:
            return None

        return TaskRecord(
            task_id=row[0],
            project_name=row[1],
            status=row[2],
            workspace_path=row[3],
            created_at=row[4],
        )

    def update_status(self, task_id: str, status: str) -> bool:
        if status not in VALID_TASK_STATUSES:
            allowed = ", ".join(sorted(VALID_TASK_STATUSES))
            raise ValueError(f"Invalid task status '{status}'. Expected one of: {allowed}")

        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE tasks SET status = ? WHERE task_id = ?",
                (status, task_id),
            )

        return cursor.rowcount > 0

    def recent_tasks(self, limit: int = 10) -> list[TaskRecord]:
        return self.list_tasks(limit=limit)

    def list_tasks(self, limit: int = 10) -> list[TaskRecord]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT task_id, project_name, status, workspace_path, created_at
                FROM tasks
                ORDER BY id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()

        return [
            TaskRecord(
                task_id=row[0],
                project_name=row[1],
                status=row[2],
                workspace_path=row[3],
                created_at=row[4],
            )
            for row in rows
        ]
