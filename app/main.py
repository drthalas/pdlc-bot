from __future__ import annotations

from dotenv import load_dotenv
from fastapi import FastAPI

from app.orchestrator import Orchestrator


load_dotenv()

app = FastAPI(title="pdlc-bot", version="0.1.0")
orchestrator = Orchestrator()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/projects")
def projects() -> dict[str, object]:
    return {"projects": [project.to_dict() for project in orchestrator.registry.list_projects()]}


@app.get("/tasks")
def tasks() -> dict[str, object]:
    return {"tasks": [record.__dict__ for record in orchestrator.store.recent_tasks(limit=20)]}
