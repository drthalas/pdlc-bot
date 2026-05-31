from __future__ import annotations

import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.ext import Application, CallbackQueryHandler, CommandHandler, ContextTypes, MessageHandler, filters

from app.codex_runner import build_codex_runner_response
from app.orchestrator import Orchestrator
from app.post_run_controls import (
    build_commit_message,
    build_show_diff_message,
    commit_task_changes,
    discard_task_changes,
    push_task_branch,
)
from app.task_messages import build_prompt_response, format_task_artifacts_response, format_task_details_response
from app.task_workspace import list_artifacts
from app.telegram_ui import (
    build_add_project_stub_keyboard,
    build_add_project_stub_message,
    build_archived_tasks_keyboard,
    build_archived_tasks_message,
    build_codex_post_run_keyboard,
    build_commit_confirm_keyboard,
    build_discard_confirm_keyboard,
    build_main_menu_keyboard,
    build_persistent_menu_keyboard,
    build_project_details_keyboard,
    build_project_details_message,
    build_project_keyboard,
    build_project_task_buttons,
    build_project_tasks_keyboard,
    build_project_tasks_message,
    build_push_confirm_keyboard,
    build_projects_message,
    build_recent_tasks_keyboard,
    build_recent_tasks_message,
    build_runbook_message,
    build_start_message,
    build_status_message,
    build_task_action_keyboard,
    build_task_subview_keyboard,
    get_menu_action,
)


logger = logging.getLogger(__name__)
NOISY_LOGGERS = ("httpx", "httpcore", "telegram", "telegram.ext", "apscheduler")
RUNNING_CODEX_STATUSES = frozenset({"coding", "codex_running", "testing"})
CODEX_CALLBACK_ACK = "Запускаю Codex..."
RECENT_TASKS_QUERY_LIMIT = 11
ARCHIVE_TASKS_LIMIT = 50
PROJECT_TASKS_QUERY_LIMIT = 1000
RECENT_TASK_CALLBACKS = frozenset({"tasks:recent", "tasks:list", "tasks:show"})


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


def is_task_running_status(status: str) -> bool:
    return status in RUNNING_CODEX_STATUSES


def build_codex_runner_started_message(task_id: str) -> str:
    return f"⏳ Codex Runner запущен для {task_id}. Это может занять время."


def final_codex_status_from_response(response: str) -> str:
    failure_markers = (
        "Working tree is dirty",
        "cannot continue",
        "Codex failed",
        "Tests: failed",
        "Branch was not created",
    )
    return "failed" if any(marker in response for marker in failure_markers) else "prompt_ready"


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
        await update.message.reply_text("Доступ запрещён.")
    return False


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await update.message.reply_text(build_start_message(), reply_markup=build_persistent_menu_keyboard())
    await update.message.reply_text("Выбери действие:", reply_markup=build_main_menu_keyboard())


async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    registered = orchestrator.registry.list_projects()
    records = orchestrator.store.list_tasks(limit=PROJECT_TASKS_QUERY_LIMIT)
    await update.message.reply_text(
        build_projects_message(registered, records),
        reply_markup=build_persistent_menu_keyboard(),
    )
    keyboard = build_project_keyboard(registered)
    if keyboard is not None:
        await update.message.reply_text("Действия с проектами:", reply_markup=keyboard)


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    records = orchestrator.store.list_tasks(limit=RECENT_TASKS_QUERY_LIMIT)
    await _reply_task_list(update, records, use_status_message=True)


async def tasks(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    records = orchestrator.store.list_tasks(limit=RECENT_TASKS_QUERY_LIMIT)
    await _reply_task_list(update, records)


async def _reply_task_list(update: Update, records, use_status_message: bool = False) -> None:
    message, keyboard = _recent_tasks_payload(records, use_status_message=use_status_message)
    await update.message.reply_text(
        message,
        reply_markup=keyboard or build_persistent_menu_keyboard(),
    )


def _recent_tasks_payload(records, use_status_message: bool = False):
    message = build_status_message(records) if use_status_message else build_recent_tasks_message(records)
    return message, build_recent_tasks_keyboard(records)


def _archived_tasks_payload(records):
    return build_archived_tasks_message(records), build_archived_tasks_keyboard(records)


async def runbook(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    await update.message.reply_text(build_runbook_message(), reply_markup=build_persistent_menu_keyboard())


async def task(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /task TASK-0001", reply_markup=build_persistent_menu_keyboard())
        return

    task_id = context.args[0].strip()
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    record = orchestrator.store.get_task(task_id)
    if record is None:
        await update.message.reply_text(f"Задача {task_id} не найдена.", reply_markup=build_persistent_menu_keyboard())
        return

    await update.message.reply_text(
        format_task_details_response(
            record,
            artifacts=list_artifacts(record.workspace_path),
        ),
        reply_markup=build_task_action_keyboard(record),
    )


async def prompt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not context.args:
        await update.message.reply_text("Использование: /prompt TASK-0001", reply_markup=build_persistent_menu_keyboard())
        return

    task_id = context.args[0].strip()
    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    record = orchestrator.store.get_task(task_id)
    response = build_prompt_response(orchestrator.store, task_id)
    reply_markup = build_task_action_keyboard(record) if record is not None else build_persistent_menu_keyboard()
    await update.message.reply_text(response.message, reply_markup=reply_markup)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    if not update.message or not update.message.text:
        return

    menu_action = get_menu_action(update.message.text)
    if menu_action == "menu":
        await start(update, context)
        return
    if menu_action == "projects":
        await projects(update, context)
        return
    if menu_action == "tasks":
        await tasks(update, context)
        return
    if menu_action == "status":
        await status(update, context)
        return
    if menu_action == "runbook":
        await runbook(update, context)
        return

    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    try:
        result = orchestrator.create_task(update.message.text)
    except Exception:
        logger.exception("Failed to create task")
        await update.message.reply_text("Не удалось создать задачу. Подробности смотри в локальных логах.")
        return

    await update.message.reply_text(
        result.response_text,
        reply_markup=build_task_action_keyboard(result.record),
    )


async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await _guard(update):
        return
    query = update.callback_query
    if query is None or query.data is None:
        return

    orchestrator: Orchestrator = context.application.bot_data["orchestrator"]
    data = query.data

    if data.startswith("task:run_codex:"):
        await query.answer(CODEX_CALLBACK_ACK)
    else:
        await query.answer()

    if data == "projects:show":
        registered = orchestrator.registry.list_projects()
        records = orchestrator.store.list_tasks(limit=PROJECT_TASKS_QUERY_LIMIT)
        await query.edit_message_text(
            build_projects_message(registered, records),
            reply_markup=build_project_keyboard(registered),
        )
        return

    if data == "menu:show":
        await query.edit_message_text(
            build_start_message(),
            reply_markup=build_main_menu_keyboard(),
        )
        return

    if data == "projects:add":
        await query.edit_message_text(
            build_add_project_stub_message(),
            reply_markup=build_add_project_stub_keyboard(),
        )
        return

    if data in RECENT_TASK_CALLBACKS:
        records = orchestrator.store.list_tasks(limit=RECENT_TASKS_QUERY_LIMIT)
        message, keyboard = _recent_tasks_payload(records)
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
        )
        return

    if data == "tasks:archive":
        records = orchestrator.store.list_tasks(limit=ARCHIVE_TASKS_LIMIT, offset=10)
        message, keyboard = _archived_tasks_payload(records)
        await query.edit_message_text(
            message,
            reply_markup=keyboard,
        )
        return

    if data == "status:show":
        records = orchestrator.store.list_tasks(limit=RECENT_TASKS_QUERY_LIMIT)
        await query.edit_message_text(
            build_status_message(records),
            reply_markup=build_recent_tasks_keyboard(records),
        )
        return

    if data == "runbook:show":
        await query.edit_message_text(build_runbook_message(), reply_markup=build_main_menu_keyboard())
        return

    if data.startswith("project:show:"):
        project_name = data.removeprefix("project:show:")
        project = orchestrator.registry.get(project_name)
        if project is None:
            await query.edit_message_text(f"Проект {project_name} не найден.")
            return
        records = orchestrator.store.list_tasks(limit=PROJECT_TASKS_QUERY_LIMIT)
        await query.edit_message_text(
            build_project_details_message(project, records),
            reply_markup=build_project_details_keyboard(project),
        )
        return

    if data.startswith("project:tasks:"):
        project_name = data.removeprefix("project:tasks:")
        project = orchestrator.registry.get(project_name)
        if project is None:
            await query.edit_message_text(f"Проект {project_name} не найден.")
            return
        records = orchestrator.store.list_tasks(limit=PROJECT_TASKS_QUERY_LIMIT)
        await query.edit_message_text(
            build_project_tasks_message(project, records),
            reply_markup=build_project_task_buttons(project, records),
        )
        return

    if data.startswith("task:details:"):
        task_id = data.removeprefix("task:details:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        await query.edit_message_text(
            format_task_details_response(record, artifacts=list_artifacts(record.workspace_path)),
            reply_markup=build_task_action_keyboard(record),
        )
        return

    if data.startswith("task:artifacts:"):
        task_id = data.removeprefix("task:artifacts:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        await query.edit_message_text(
            format_task_artifacts_response(record, artifacts=list_artifacts(record.workspace_path)),
            reply_markup=build_task_subview_keyboard(record.task_id),
        )
        return

    if data.startswith("task:prompt:"):
        task_id = data.removeprefix("task:prompt:")
        record = orchestrator.store.get_task(task_id)
        response = build_prompt_response(orchestrator.store, task_id)
        reply_markup = build_task_subview_keyboard(record.task_id) if record is not None else None
        await query.edit_message_text(response.message, reply_markup=reply_markup)
        return

    if data.startswith("task:run_codex:"):
        task_id = data.removeprefix("task:run_codex:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        if is_task_running_status(record.status):
            await query.edit_message_text(
                f"Задача {task_id} уже выполняется.",
                reply_markup=build_task_action_keyboard(record),
            )
            return
        orchestrator.store.update_status(task_id, "codex_running")
        await query.edit_message_text(build_codex_runner_started_message(task_id))
        record = orchestrator.store.get_task(task_id) or record
        response = build_codex_runner_response(record)
        orchestrator.store.update_status(task_id, final_codex_status_from_response(response))
        record = orchestrator.store.get_task(task_id) or record
        reply_markup = build_task_action_keyboard(record)
        await query.edit_message_text(
            response,
            reply_markup=reply_markup,
        )
        return

    if data.startswith("task:show_diff:"):
        task_id = data.removeprefix("task:show_diff:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        await query.edit_message_text(
            build_show_diff_message(record),
            reply_markup=build_codex_post_run_keyboard(record.task_id),
        )
        return

    if data.startswith("task:tests_again:"):
        task_id = data.removeprefix("task:tests_again:")
        await query.edit_message_text(
            "Повторный запуск тестов пока не реализован.",
            reply_markup=build_codex_post_run_keyboard(task_id),
        )
        return

    if data.startswith("task:commit:"):
        task_id = data.removeprefix("task:commit:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        await query.edit_message_text(
            f"Закоммитить локальные изменения для {task_id}?\n\nСообщение: {build_commit_message(record)}",
            reply_markup=build_commit_confirm_keyboard(task_id),
        )
        return

    if data.startswith("task:confirm_commit:"):
        task_id = data.removeprefix("task:confirm_commit:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        result = commit_task_changes(record)
        if result.ok:
            orchestrator.store.update_status(task_id, "committed")
            record = orchestrator.store.get_task(task_id) or record
        await query.edit_message_text(
            result.message,
            reply_markup=build_task_action_keyboard(record),
        )
        return

    if data.startswith("task:push:"):
        task_id = data.removeprefix("task:push:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        await query.edit_message_text(
            f"Сделать Push для {task_id}?\n\nБудет выполнено `git push -u origin <branch>`.",
            reply_markup=build_push_confirm_keyboard(task_id),
        )
        return

    if data.startswith("task:confirm_push:"):
        task_id = data.removeprefix("task:confirm_push:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        result = push_task_branch(record)
        await query.edit_message_text(result.message, reply_markup=build_task_action_keyboard(record))
        return

    if data.startswith("task:discard:"):
        task_id = data.removeprefix("task:discard:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        await query.edit_message_text(
            f"Откатить локальные изменения для {task_id}?\n\nБудет выполнено `git reset --hard` и `git checkout main`.",
            reply_markup=build_discard_confirm_keyboard(task_id),
        )
        return

    if data.startswith("task:confirm_discard:"):
        task_id = data.removeprefix("task:confirm_discard:")
        record = orchestrator.store.get_task(task_id)
        if record is None:
            await query.edit_message_text(f"Задача {task_id} не найдена.")
            return
        result = discard_task_changes(record)
        await query.edit_message_text(result.message, reply_markup=build_task_action_keyboard(record))
        return

    await query.edit_message_text("Неизвестное действие.")


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
    application.add_handler(CommandHandler("runbook", runbook))
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
