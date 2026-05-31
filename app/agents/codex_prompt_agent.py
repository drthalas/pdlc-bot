from __future__ import annotations

from collections.abc import Iterable

from app.agents.intake_agent import IntakeResult


BASE_CONTEXT_FILES = [
    "docs/PROMPT_BUILDER.md",
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
    "Все пользовательские Telegram-тексты должны быть на русском по умолчанию.",
    "Technical artifact filenames, internal status values и code identifiers могут оставаться на английском.",
    "Codex Runner не должен делать commit, push или deploy без явного approval.",
    "Mac mini — execution runtime.",
    "Railway dashboard / PDLC Control Center запланирован позже.",
    "Tester/QA Agent обязателен в future roadmap.",
    "Перед изменениями держи scope минимальным и не трогай unrelated files.",
]


TELEGRAM_KEYWORDS = (
    "telegram",
    "бот",
    "bot",
    "кноп",
    "button",
    "menu",
    "меню",
    "ux",
    "task",
    "tasks",
    "prompt",
    "callback",
)

CODEX_RUNNER_KEYWORDS = (
    "codex",
    "runner",
    "run codex",
    "subprocess",
    "branch",
    "git",
    "diff",
    "commit",
    "push",
)

TELEGRAM_FILES = [
    "app/telegram_bot.py",
    "app/telegram_ui.py",
    "app/task_messages.py",
    "app/task_store.py",
    "app/post_run_controls.py",
    "tests/test_telegram_ui.py",
    "tests/test_task_messages.py",
]

CODEX_RUNNER_FILES = [
    "app/codex_runner.py",
    "app/post_run_controls.py",
    "docs/CODEX_RUNNER_V0.md",
    "tests/test_codex_runner.py",
    "tests/test_post_run_controls.py",
]

MAC_MINI_FILES = [
    "docs/MAC_MINI_RUNBOOK.md",
    "README.md",
    "docs/ROADMAP.md",
]

BASIC_FILES = [
    "README.md",
    "PROJECT_CONTEXT.md",
    "TASKS.md",
    "DECISIONS.md",
]


def context_files_for_request(raw_request: str) -> list[str]:
    lowered = raw_request.lower()
    files = list(BASE_CONTEXT_FILES)
    if any(keyword in lowered for keyword in MAC_MINI_KEYWORDS):
        files.append(MAC_MINI_CONTEXT_FILE)
    files.append("Relevant docs/*.md files for the task topic")
    return files


def _matches(raw_request: str, keywords: tuple[str, ...]) -> bool:
    lowered = raw_request.lower()
    return any(keyword in lowered for keyword in keywords)


def task_focus(raw_request: str) -> str:
    if _matches(raw_request, CODEX_RUNNER_KEYWORDS):
        return "codex_runner"
    if _matches(raw_request, MAC_MINI_KEYWORDS):
        return "mac_mini"
    if _matches(raw_request, TELEGRAM_KEYWORDS):
        return "telegram_ux"
    return "general"


def suggested_files_for_request(raw_request: str) -> list[str]:
    focus = task_focus(raw_request)
    if focus == "telegram_ux":
        return TELEGRAM_FILES
    if focus == "codex_runner":
        return CODEX_RUNNER_FILES
    if focus == "mac_mini":
        return MAC_MINI_FILES
    return BASIC_FILES


def task_brief(raw_request: str) -> str:
    return (
        "Разобрать короткую задачу пользователя, уточнить её по коду проекта и внести минимальное "
        f"изменение без расширения scope: {raw_request}"
    )


def current_behavior_for_request(raw_request: str) -> str:
    focus = task_focus(raw_request)
    if focus == "telegram_ux":
        return (
            "Telegram UX сейчас недостаточно точно отражает ожидаемый сценарий пользователя: "
            "сообщения, кнопки или списки задач могут быть непонятными, слишком общими или не сохранять нужный state."
        )
    if focus == "codex_runner":
        return (
            "Codex Runner развивается поэтапно: важно не ослабить safety-гарантии, не запустить Codex без explicit action "
            "и не добавить commit/push/deploy поведение без отдельного approval."
        )
    if focus == "mac_mini":
        return (
            "Mac mini является runtime-средой через launchd; документация и deployment UX должны помогать проверять service, "
            "логи и deployed version без раскрытия token или локальных секретов."
        )
    return "Текущее поведение нужно проверить по коду и документации, потому что запрос пользователя короткий и требует аккуратного уточнения через existing patterns."


def desired_behavior_for_request(raw_request: str) -> str:
    focus = task_focus(raw_request)
    if focus == "telegram_ux":
        return (
            "Пользователь должен видеть понятный русский Telegram UX: релевантные кнопки, короткие сообщения, сохранение старых команд "
            "и корректные callback actions без потери контекста."
        )
    if focus == "codex_runner":
        return (
            "Runner должен выполнять только явно разрешённый безопасный шаг, сохранять artifacts, ясно сообщать результат в Telegram "
            "и не делать commit/push/deploy."
        )
    if focus == "mac_mini":
        return (
            "Runbook/deployment flow должен быть понятным, безопасным и применимым к Mac mini runtime без публикации token или полного .env."
        )
    return "После изменения поведение должно прямо закрывать пользовательский запрос, оставаться маленьким по scope и иметь проверяемые тесты."


def implementation_plan_for_request(raw_request: str) -> list[str]:
    focus = task_focus(raw_request)
    if focus == "telegram_ux":
        return [
            "Прочитать Telegram handlers и UI helper functions, чтобы понять текущий routing команд, callbacks и keyboards.",
            "Найти место, где формируется нужный текст, список, кнопка или task details.",
            "Сделать пользовательские Telegram-тексты на русском, оставив callback_data/internal identifiers на английском.",
            "Сохранить совместимость старых slash-команд и existing inline/persistent keyboards.",
            "Проверить, что callback_data остаётся не длиннее 64 bytes.",
            "Добавить или обновить focused tests для affected Telegram UI/helper behavior.",
            "Запустить `.venv/bin/pytest` и `.venv/bin/python -m app.main`.",
        ]
    if focus == "codex_runner":
        return [
            "Прочитать Codex Runner spec, текущую runner implementation и post-run controls.",
            "Определить самый маленький безопасный runner step для запроса.",
            "Убедиться, что Codex не запускается автоматически и все опасные действия требуют explicit approval.",
            "Если нужны subprocess calls, разрешить только конкретные команды с `shell=False` и timeout.",
            "Сохранять все новые результаты в task artifacts с понятными именами.",
            "Покрыть subprocess/git/Codex поведение mocks в тестах, не запуская реальный Codex CLI.",
            "Запустить `.venv/bin/pytest` и `.venv/bin/python -m app.main`.",
        ]
    if focus == "mac_mini":
        return [
            "Прочитать Mac mini runbook, README и roadmap, чтобы не расходиться с runtime model.",
            "Проверить, что инструкции используют Mac mini как execution runtime и не раскрывают token/.env.",
            "Обновить только релевантные operational docs или UI text.",
            "Не менять launchd/service behavior без отдельного explicit request.",
            "Добавить/обновить tests, если меняется bot behavior или generated artifacts.",
            "Запустить `.venv/bin/pytest` и `.venv/bin/python -m app.main`.",
        ]
    return [
        "Прочитать project memory files и suggested files.",
        "Найти existing patterns для похожего поведения.",
        "Сформулировать минимальное изменение, которое прямо закрывает запрос.",
        "Внести scoped code/docs/tests changes без unrelated refactor.",
        "Добавить focused tests на новое поведение или regression risk.",
        "Запустить `.venv/bin/pytest` и `.venv/bin/python -m app.main`.",
    ]


def acceptance_criteria_for_request(raw_request: str) -> list[str]:
    focus = task_focus(raw_request)
    if focus == "telegram_ux":
        return [
            "Пользовательские Telegram-тексты на русском там, где они видны пользователю.",
            "Нужные кнопки/пункты меню отображаются в соответствующих сообщениях.",
            "callback_data для inline-кнопок не превышает 64 bytes.",
            "Старые команды `/start`, `/projects`, `/status`, `/tasks`, `/task`, `/prompt` не сломаны, если затронут Telegram UX.",
            "Добавлены или обновлены focused tests для нового UX.",
        ]
    if focus == "codex_runner":
        return [
            "Codex CLI не запускается без explicit user action.",
            "Runner не делает commit, push, PR или deploy.",
            "Все новые runner results сохраняются в task artifacts.",
            "Subprocess/git behavior покрыт tests через mocks, без запуска реального Codex CLI.",
            "Safety checks для dirty tree, approvals и protected files сохранены или усилены.",
        ]
    if focus == "mac_mini":
        return [
            "Инструкции не выводят Telegram token, полный `.env` или приватные локальные значения.",
            "Mac mini описан как execution runtime, а MacBook как development machine.",
            "launchd/service/log commands понятны и не требуют sudo, если это не оговорено отдельно.",
            "Документация явно не запускает Codex CLI/GitHub automation без отдельного approval.",
        ]
    return [
        "Изменение реализует смысл пользовательского запроса.",
        "Scope минимальный, unrelated files не тронуты.",
        "Добавлены или обновлены релевантные тесты.",
        "Все проверки проходят.",
    ]


def safety_constraints_for_request(raw_request: str) -> list[str]:
    return [
        "Не запускать Telegram polling/API во время coding task без отдельного запроса.",
        "Не запускать реальный Codex CLI или `run_codex.sh`, если задача явно не просит runtime execution.",
        "Не делать commit, push, PR или deploy без explicit approval.",
        "Не менять `.env` и не выводить secrets/token.",
        "Не трогать `config/projects.yaml`, если задача явно не просит локальную настройку runtime.",
        "Не выполнять destructive git commands без отдельного approval.",
    ]


def out_of_scope_for_request(raw_request: str) -> list[str]:
    focus = task_focus(raw_request)
    items = [
        "Commit/push/deploy.",
        "Изменения в `.env`, local runtime config и secrets.",
        "Unrelated refactor или переписывание архитектуры целиком.",
    ]
    if focus != "codex_runner":
        items.append("Изменения Codex Runner execution flow, если задача не про Runner.")
    if focus != "mac_mini":
        items.append("Mac mini deployment/launchd changes, если задача не про deployment.")
    return items


def verification_commands(intake: IntakeResult) -> list[str]:
    commands = list(intake.project.test_commands) if intake.project and intake.project.test_commands else []
    for fallback in (".venv/bin/pytest", ".venv/bin/python -m app.main"):
        if fallback not in commands:
            commands.append(fallback)
    return commands


def _bullet_list(items: Iterable[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def _numbered_list(items: list[str]) -> str:
    return "\n".join(f"{index}. {item}" for index, item in enumerate(items, start=1))


class CodexPromptAgent:
    def create_prompt(self, task_id: str, intake: IntakeResult, brief: str, plan: str) -> str:
        project = intake.project
        project_name = project.name if project else "UNKNOWN_PROJECT"
        local_path = project.local_path if project else "UNKNOWN_LOCAL_PATH"
        repo_url = project.repo_url if project else "UNKNOWN_REPO_URL"
        context_files = _bullet_list(context_files_for_request(intake.raw_request))
        project_rules = _bullet_list(PROJECT_RULES)
        suggested_files = _bullet_list(suggested_files_for_request(intake.raw_request))
        implementation_plan = _numbered_list(implementation_plan_for_request(intake.raw_request))
        acceptance_criteria = _bullet_list(acceptance_criteria_for_request(intake.raw_request))
        safety_constraints = _bullet_list(safety_constraints_for_request(intake.raw_request))
        out_of_scope = _bullet_list(out_of_scope_for_request(intake.raw_request))
        verification = _bullet_list(f"`{command}`" for command in verification_commands(intake))

        return f"""# Ты Codex, работаешь над {task_id}

## Target project

- Project: {project_name}
- Repository URL: {repo_url}
- Local path: {local_path}

## User request

{intake.raw_request}

## Project memory / context

Перед изменениями прочитай эти project memory/context files, если они есть:

{context_files}

## Permanent project rules

{project_rules}

## Task brief

{task_brief(intake.raw_request)}

## Current behavior

{current_behavior_for_request(intake.raw_request)}

## Desired behavior

{desired_behavior_for_request(intake.raw_request)}

## Suggested files to inspect

{suggested_files}

## Implementation plan

{implementation_plan}

## Acceptance criteria

{acceptance_criteria}

## Safety constraints

{safety_constraints}

## Out of scope

{out_of_scope}

## Verification

{verification}

## Report format

После работы верни короткий отчёт:

- changed files;
- что изменено в поведении;
- какие tests/checks запущены и результат;
- риски/TODO;
- подтверждение, что commit/push/deploy не выполнялись без approval.

## Existing generated analysis

Ниже исходные artifacts от PDLC agents. Используй их как дополнительный контекст, но приоритет у User request, Project memory и правил выше.

{brief}

{plan}
"""
