from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters

from app.orchestrator import Orchestrator


logger = logging.getLogger(__name__)


def _allowed_user_ids() -> set[int]:
    raw_value = os.getenv("TELEGRAM_ALLOWED_USER_IDS", "")
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


def _is_allowed(update: Update) -> bool:
    allowed = _allowed_user_ids()
    if not allowed:
        return True
    user = update.effective_user
    return user is not None and user.id in allowed


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
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


def main() -> None:
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
