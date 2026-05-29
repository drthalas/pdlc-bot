from __future__ import annotations

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.orchestrator import Orchestrator


logger = logging.getLogger(__name__)


def parse_allowed_user_ids(raw_value: str) -> set[int]:
    allowed: set[int] = set()
    for item in raw_value.split(","):
        item = item.strip()
        if not item:
            continue
        try:
            allowed.add(int(item))
        except ValueError:
            logger.warning("Ignoring invalid TELEGRAM_ALLOWED_USER_IDS entry: %s", item)
    return allowed


def is_user_allowed(user_id: int | None, allowed_user_ids: set[int]) -> bool:
    if not allowed_user_ids:
        return True
    return user_id is not None and user_id in allowed_user_ids


def _allowed_user_ids() -> set[int]:
    return parse_allowed_user_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS", ""))


def _is_allowed(update: Update) -> bool:
    user = update.effective_user
    user_id = user.id if user is not None else None
    return is_user_allowed(user_id, _allowed_user_ids())


async def _guard(update: Update) -> bool:
    if _is_allowed(update):
        return True
    if update.message:
        await update.message.reply_text("Access denied.")
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await update.message.reply_text(
        "PDLC bot is ready. Send a development task, or use /projects and /status."
    )


async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    registered = orchestrator.registry.list_projects()
    if not registered:
        await update.message.reply_text("No projects configured. Create config/projects.yaml first.")
        return

    lines = ["Configured projects:"]
    for project in registered:
        alias_text = f" ({', '.join(project.aliases)})" if project.aliases else ""
        lines.append(f"- {project.name}{alias_text}")
    await update.message.reply_text("\n".join(lines))


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    records = orchestrator.store.recent_tasks(limit=10)
    if not records:
        await update.message.reply_text("No tasks created yet.")
        return

    lines = ["Recent tasks:"]
    for record in records:
        project_name = record.project_name or "unknown project"
        lines.append(f"- {record.task_id}: {record.status}, {project_name}")
    await update.message.reply_text("\n".join(lines))


async def task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /task TASK-0001")
        return

    task_id = context.args[0].strip()
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    record = orchestrator.store.get_task(task_id)
    if record is None:
        await update.message.reply_text(f"Task {task_id} not found.")
        return

    project_name = record.project_name or "not detected"
    lines = [
        record.task_id,
        "",
        f"Project: {project_name}",
        f"Status: {record.status}",
        f"Workspace: {record.workspace_path}",
    ]

    workspace_path = Path(record.workspace_path)
    if workspace_path.exists() and workspace_path.is_dir():
        artifacts = sorted(path.name for path in workspace_path.iterdir() if path.is_file())
        if artifacts:
            lines.extend(["", "Artifacts:"])
            lines.extend(f"- {artifact}" for artifact in artifacts)

    await update.message.reply_text("\n".join(lines))


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not update.message or not update.message.text:
        return

    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    try:
        result = orchestrator.create_task(update.message.text)
    except Exception:
        logger.exception("Failed to create task")
        await update.message.reply_text("Could not create the task. Check local logs for details.")
        return

    await update.message.reply_text(result.response_text)


def build_application() -> Application:
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    logging.basicConfig(level=logging.INFO)
    application = Application.builder().token(token).build()
    application.bot_data["orchestrator"] = Orchestrator()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("projects", projects))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("task", task))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


def main() -> None:
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
