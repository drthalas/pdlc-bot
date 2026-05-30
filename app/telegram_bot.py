from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.orchestrator import Orchestrator
from app.task_messages import build_prompt_response, format_task_details_response
from app.task_workspace import list_artifacts
from app.telegram_ui import (
    build_main_menu_keyboard,
    build_project_details_message,
    build_project_keyboard,
    build_projects_message,
    build_recent_tasks_keyboard,
    build_recent_tasks_message,
    build_start_message,
    build_status_message,
    build_task_actions_keyboard,
    build_task_details_keyboard,
)


logger = logging.getLogger(__name__)
NOISY_LOGGERS = ("httpx", "httpcore", "telegram", "telegram.ext", "apscheduler")


def configure_safe_logging() -> None:
    logging.basicConfig(level=logging.INFO)
    logging.getLogger("app").setLevel(logging.INFO)
    for logger_name in NOISY_LOGGERS:
        logging.getLogger(logger_name).setLevel(logging.WARNING)


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
    await update.message.reply_text(build_start_message(), reply_markup=build_main_menu_keyboard())


async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    registered = orchestrator.registry.list_projects()
    await update.message.reply_text(
        build_projects_message(registered),
        reply_markup=build_project_keyboard(registered),
    )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    records = orchestrator.store.list_tasks(limit=10)
    await update.message.reply_text(
        build_status_message(records),
        reply_markup=build_recent_tasks_keyboard(records),
    )


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    records = orchestrator.store.list_tasks(limit=10)
    await update.message.reply_text(
        build_recent_tasks_message(records),
        reply_markup=build_recent_tasks_keyboard(records),
    )


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

    await update.message.reply_text(
        format_task_details_response(
            record,
            artifacts=list_artifacts(record.workspace_path),
        ),
        reply_markup=build_task_details_keyboard(record.task_id),
    )


async def prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Usage: /prompt TASK-0001")
        return

    task_id = context.args[0].strip()
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    response = build_prompt_response(orchestrator.store, task_id)
    await update.message.reply_text(response.message)


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

    await update.message.reply_text(
        result.response_text,
        reply_markup=build_task_actions_keyboard(result.record.task_id),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    query = update.callback_query
    if query is None or query.data is None:
        return

    await query.answer()
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    data = query.data

    if data == "projects:show":
        registered = orchestrator.registry.list_projects()
        await query.edit_message_text(
            build_projects_message(registered),
            reply_markup=build_project_keyboard(registered),
        )
        return

    if data == "tasks:recent":
        records = orchestrator.store.list_tasks(limit=10)
        await query.edit_message_text(
            build_recent_tasks_message(records),
            reply_markup=build_recent_tasks_keyboard(records),
        )
        return

    if data == "status:show":
        records = orchestrator.store.list_tasks(limit=10)
        await query.edit_message_text(
            build_status_message(records),
            reply_markup=build_recent_tasks_keyboard(records),
        )
        return

    if data.startswith("project:show:"):
        project_name = data.removeprefix("project:show:")
        project = orchestrator.registry.get(project_name)
        if project is None:
            await query.edit_message_text(f"Project {project_name} not found.")
            return
        await query.edit_message_text(build_project_details_message(project))
        return

    if data.startswith("task:details:"):
        task_id = data.removeprefix("task:details:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Task {task_id} not found.")
            return
        await query.edit_message_text(
            format_task_details_response(record, artifacts=list_artifacts(record.workspace_path)),
            reply_markup=build_task_details_keyboard(record.task_id),
        )
        return

    if data.startswith("task:prompt:"):
        task_id = data.removeprefix("task:prompt:")
        response = build_prompt_response(orchestrator.store, task_id)
        await query.edit_message_text(response.message)
        return

    await query.edit_message_text("Unknown action.")


def build_application() -> Application:
    configure_safe_logging()
    load_dotenv()
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is required")

    application = Application.builder().token(token).build()
    application.bot_data["orchestrator"] = Orchestrator()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("projects", projects))
    application.add_handler(CommandHandler("status", status))
    application.add_handler(CommandHandler("tasks", tasks))
    application.add_handler(CommandHandler("task", task))
    application.add_handler(CommandHandler("prompt", prompt))
    application.add_handler(CallbackQueryHandler(handle_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    return application


def main() -> None:
    application = build_application()
    application.run_polling()


if __name__ == "__main__":
    main()
