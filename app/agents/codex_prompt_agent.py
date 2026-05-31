from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

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

TASK_CARD_KEYWORDS = (
    "карточк",
    "детали задачи",
    "technical details",
    "технические детали",
    "технические файлы",
    "artifacts",
    "artifact",
    "архив",
    "последние 10",
    "старые задачи",
    "список задач",
    "progress",
    "прогресс",
    "этап",
    "статус",
)

PROJECT_UX_KEYWORDS = (
    "/projects",
    "раздел проекты",
    "раздел “проекты”",
    "раздел \"проекты\"",
    "проекты",
    "проектов",
    "карточка проекта",
    "карточку проекта",
    "карточке проекта",
    "карточки проекта",
    "карточки проектов",
    "карточек проектов",
    "project card",
    "project cards",
    "project details",
    "детали проекта",
    "задачи проекта",
    "задачами проекта",
    "github url",
    "repo url",
    "repo_url",
    "local_path",
    "описание",
    "добавить проект",
)

CODEX_RUNNER_KEYWORDS = (
    "codex",
    "runner",
    "run codex",
    "subprocess",
    "branch",
    "git status",
    "git check",
    "git branch",
    "git checkout",
    "git diff",
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

TASK_CARD_FILES = [
    "app/telegram_bot.py",
    "app/telegram_ui.py",
    "app/task_messages.py",
    "app/task_store.py",
    "app/post_run_controls.py",
    "tests/test_telegram_ui.py",
    "tests/test_task_messages.py",
    "README.md",
    "docs/CODEX_RUNNER_V0.md",
    "DECISIONS.md",
]

PROJECT_UX_FILES = [
    "app/telegram_bot.py",
    "app/telegram_ui.py",
    "app/project_registry.py",
    "app/task_store.py",
    "config/projects.example.yaml",
    "tests/test_telegram_ui.py",
    "tests/test_project_registry.py",
    "tests/test_task_store.py",
    "README.md",
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


@dataclass(frozen=True)
class RequirementExtraction:
    goal: str
    entities: list[str]
    actions: list[str]
    constraints: list[str]
    expected_results: list[str]
    current_behavior: list[str]
    implementation_steps: list[str]
    acceptance_criteria: list[str]
    out_of_scope: list[str]
    categories: list[str]


def _add_unique(items: list[str], item: str) -> None:
    if item not in items:
        items.append(item)


def _contains_any(lowered: str, keywords: tuple[str, ...]) -> bool:
    return any(keyword in lowered for keyword in keywords)


def _is_project_card_request(lowered: str) -> bool:
    project_card_phrases = (
        "карточка проекта",
        "карточку проекта",
        "карточке проекта",
        "карточки проекта",
        "карточки проектов",
        "карточек проектов",
        "карточками проектов",
        "project card",
        "project cards",
        "project details",
        "детали проекта",
    )
    return any(phrase in lowered for phrase in project_card_phrases)


def _is_task_card_request(lowered: str) -> bool:
    task_card_phrases = (
        "карточка задачи",
        "карточку задачи",
        "карточке задачи",
        "карточки задачи",
        "карточек задач",
        "task card",
        "task details",
        "детали задачи",
        "/task",
        "task-id",
        "task id",
    )
    task_stage_phrases = (
        "этап задачи",
        "текущий этап задачи",
        "прогресс задачи",
        "progress checklist",
        "prompt, codex, tests, review, commit",
        "codex/tests/review/commit",
        "codex, tests, review, commit",
    )
    return any(phrase in lowered for phrase in task_card_phrases + task_stage_phrases)


def extract_requirements(raw_request: str) -> RequirementExtraction:
    lowered = raw_request.lower()
    goal = " ".join(raw_request.strip().split())
    entities: list[str] = []
    actions: list[str] = []
    constraints: list[str] = []
    expected: list[str] = []
    current: list[str] = []
    steps: list[str] = []
    acceptance: list[str] = []
    out_of_scope: list[str] = []
    categories: list[str] = []

    if _contains_any(lowered, TELEGRAM_KEYWORDS):
        _add_unique(categories, "telegram_ux")
        _add_unique(entities, "Telegram UX")
        _add_unique(actions, "обновить пользовательские сообщения, кнопки или callbacks")
        _add_unique(constraints, "Все пользовательские Telegram-тексты должны быть на русском.")
        _add_unique(expected, "- Пользователь должен видеть понятный русский Telegram UX: релевантные кнопки, короткие сообщения, сохранение старых команд и корректные callback actions без потери контекста.")
        _add_unique(acceptance, "Все пользовательские Telegram-тексты на русском.")
        _add_unique(acceptance, "Пользовательские Telegram-тексты на русском там, где они видны пользователю.")
        _add_unique(acceptance, "Нужные кнопки/пункты меню отображаются в соответствующих сообщениях.")
        _add_unique(acceptance, "Callback data не длиннее 64 символов.")
        _add_unique(acceptance, "callback_data для inline-кнопок не превышает 64 bytes.")
        _add_unique(acceptance, "Старые команды не сломаны.")
        _add_unique(acceptance, "Старые команды `/start`, `/projects`, `/status`, `/tasks`, `/task`, `/prompt` не сломаны, если затронут Telegram UX.")
        _add_unique(acceptance, "Добавлены или обновлены focused tests для нового UX.")

    if _contains_any(lowered, PROJECT_UX_KEYWORDS):
        _add_unique(categories, "project_management_ux")
        _add_unique(entities, "раздел `/projects`")
        _add_unique(entities, "карточки проектов")
        _add_unique(current, "- `/projects` показывает список проектов слишком плоско и не помогает понять, чем проект является.")
        _add_unique(current, "- В списке проектов не видно описание, GitHub URL, runtime/local status и количество задач.")
        _add_unique(current, "- Project details не выглядят как отдельная карточка проекта с понятными действиями.")
        _add_unique(expected, "- `/projects` показывает проекты с описанием, GitHub URL, статусом и количеством задач.")
        _add_unique(expected, "- Каждый проект кликабельный и открывает карточку проекта.")
        _add_unique(expected, "- Карточка проекта показывает название, aliases, stack, GitHub URL, local path/status, описание и последние задачи этого проекта.")
        _add_unique(expected, "- Карточка проекта показывает description, aliases, stack, repo_url, local_path и status.")
        _add_unique(expected, "- В карточке проекта есть кнопки `Задачи проекта`, `Назад к проектам`, `Добавить проект`.")
        _add_unique(steps, "Найти handlers и callbacks для `/projects` и `project:show:*`.")
        _add_unique(steps, "Проверить, какие поля доступны в `ProjectRegistry` и `config/projects.example.yaml`.")
        _add_unique(steps, "Добавить или обновить helper для списка проектов с описанием, GitHub URL, статусом и количеством задач.")
        _add_unique(steps, "Добавить user-friendly карточку проекта с aliases, stack, repo URL, local path/status и последними задачами проекта.")
        _add_unique(acceptance, "`/projects` показывает проекты с описанием, GitHub URL, статусом и количеством задач.")
        _add_unique(acceptance, "Проект кликабельный и открывает карточку проекта.")
        _add_unique(acceptance, "Карточка проекта показывает description, aliases, stack, repo_url, local_path и status.")
        _add_unique(acceptance, "Есть кнопка `Назад к проектам`.")
        _add_unique(acceptance, "callback_data для новых project buttons не длиннее 64 bytes.")
        _add_unique(acceptance, "Существующая команда `/projects` не сломана.")

    if "описан" in lowered:
        _add_unique(entities, "описание проекта")
        _add_unique(expected, "- Карточка проекта показывает описание проекта.")
        _add_unique(acceptance, "Карточка проекта показывает описание проекта.")

    if "github url" in lowered or "repo url" in lowered or "github" in lowered:
        _add_unique(entities, "GitHub URL проекта")
        _add_unique(expected, "- Карточка проекта показывает GitHub URL.")
        _add_unique(acceptance, "Карточка проекта показывает GitHub URL.")

    if "задачи проекта" in lowered or "задачами проекта" in lowered:
        _add_unique(entities, "задачи выбранного проекта")
        _add_unique(actions, "показать задачи конкретного проекта")
        _add_unique(current, "- Нельзя быстро открыть задачи конкретного проекта.")
        _add_unique(expected, "- `Задачи проекта` показывает только задачи выбранного проекта.")
        _add_unique(steps, "Реализовать callback `Задачи проекта`, который фильтрует задачи по `project_name`.")
        _add_unique(acceptance, "Карточка проекта показывает последние задачи только этого проекта.")
        _add_unique(acceptance, "Есть кнопка `Задачи проекта`.")

    if "добавить проект" in lowered:
        _add_unique(entities, "кнопка `Добавить проект`")
        _add_unique(actions, "добавить безопасную заглушку добавления проекта")
        _add_unique(current, "- Нет отдельной кнопки `Добавить проект` даже как безопасной заглушки.")
        _add_unique(expected, "- `Добавить проект` пока работает как заглушка: объясняет будущий flow, ничего не клонирует и не меняет config.")
        _add_unique(steps, "Реализовать `Добавить проект` как безопасную заглушку без clone, git commands и изменения `config/projects.yaml`.")
        _add_unique(acceptance, "Есть кнопка `Добавить проект`.")
        _add_unique(acceptance, "`Добавить проект` пока заглушка: ничего не клонирует и не меняет config.")
        _add_unique(constraints, "Не клонировать репозитории и не менять `config/projects.yaml` для заглушки добавления проекта.")
        _add_unique(out_of_scope, "Не клонировать репозитории.")
        _add_unique(out_of_scope, "Не менять `config/projects.yaml`.")
        _add_unique(out_of_scope, "Не реализовывать полноценный onboarding нового проекта.")
        _add_unique(out_of_scope, "`Добавить проект` должен быть только безопасной заглушкой.")

    if _is_task_card_request(lowered):
        _add_unique(categories, "task_card_ux")
        _add_unique(entities, "карточка задачи")
        _add_unique(current, "- `/task TASK-ID` показывает слишком много технической информации и artifacts.")
        _add_unique(current, "- Пользователю сложно понять текущий этап задачи.")
        _add_unique(current, "- В карточке задачи не видно прогресс: prompt, Codex, tests, review, commit.")
        _add_unique(expected, "- Карточка задачи показывает TASK-ID, название, проект, текущий статус и текущий этап.")
        _add_unique(expected, "- Карточка показывает прогресс: задача создана, prompt готов, Codex выполнен или нет, тесты пройдены или нет, review ожидается или выполнен, commit сделан или нет.")
        _add_unique(expected, "- Кнопки зависят от текущего состояния задачи.")
        _add_unique(steps, "Найти, где формируется `/task TASK-ID` и Task details callback.")
        _add_unique(steps, "Вынести или обновить helper для user-friendly task card.")
        _add_unique(steps, "Добавить определение display state задачи по status и artifacts.")
        _add_unique(steps, "Убедиться, что post-run задачи не показывают `▶️ Запустить Codex` как основное действие.")
        _add_unique(acceptance, "`/task TASK-ID` не показывает raw artifacts по умолчанию.")
        _add_unique(acceptance, "Карточка задачи содержит название, проект, статус, текущий этап и progress checklist.")
        _add_unique(acceptance, "Post-run task показывает diff/tests/review/commit/discard, а не `▶️ Запустить Codex`.")

    if "технические файлы" in lowered or "технические детали" in lowered or "artifacts" in lowered:
        _add_unique(entities, "технические artifacts")
        _add_unique(actions, "скрыть технические файлы из основного пользовательского экрана")
        _add_unique(current, "- Технические файлы не должны показываться по умолчанию.")
        _add_unique(expected, "- Технические artifacts скрыты за кнопкой `🛠 Технические детали`.")
        _add_unique(steps, "Скрыть raw artifact list из карточки задачи.")
        _add_unique(steps, "Добавить кнопку `🛠 Технические детали` и отдельный callback для artifacts.")
        _add_unique(acceptance, "Есть кнопка `🛠 Технические детали`.")
        _add_unique(acceptance, "Technical details callback показывает artifacts отдельно.")

    if "список задач" in lowered or "/tasks" in lowered or "последние 10" in lowered:
        _add_unique(entities, "список задач")
        _add_unique(current, "- `/tasks` и Recent tasks недостаточно понятно показывают, о чём задача.")
        _add_unique(expected, "- `/tasks` показывает максимум 10 последних задач.")
        _add_unique(expected, "- Задачи в списке показываются с коротким названием из `input.md`.")
        _add_unique(steps, "Обновить `/tasks` и Recent tasks: максимум 10 задач.")
        _add_unique(steps, "Добавить или переиспользовать task title extraction из `input.md`.")
        _add_unique(acceptance, "`/tasks` показывает максимум 10 последних задач.")
        _add_unique(acceptance, "Task title берётся из `input.md`.")
        _add_unique(acceptance, "Длинный title обрезается до 60–80 символов.")
        _add_unique(acceptance, "Missing `input.md` даёт fallback на `TASK-ID`.")

    if "архив" in lowered or "старые" in lowered:
        _add_unique(entities, "архив задач")
        _add_unique(current, "- Основной список задач может разрастаться.")
        _add_unique(current, "- Старые задачи не вынесены в архив.")
        _add_unique(expected, "- Старые задачи доступны через `📦 Архив задач`.")
        _add_unique(steps, "Добавить `📦 Архив задач` для старых задач.")
        _add_unique(acceptance, "Если задач больше 10, есть кнопка `📦 Архив задач`.")
        _add_unique(acceptance, "Архив показывает более старые задачи.")

    if _contains_any(lowered, CODEX_RUNNER_KEYWORDS):
        _add_unique(categories, "codex_runner")
        _add_unique(entities, "Codex Runner")
        _add_unique(actions, "изменить runner flow с сохранением safety guarantees")
        _add_unique(current, "- Codex Runner требует строгих safety checks для git, subprocess, commit, push и deploy.")
        _add_unique(expected, "- Runner выполняет только явно разрешённый безопасный шаг и сохраняет artifacts.")
        _add_unique(steps, "Прочитать Codex Runner spec, текущую runner implementation и post-run controls.")
        _add_unique(steps, "Покрыть subprocess/git/Codex поведение mocks в тестах, не запуская реальный Codex CLI.")
        _add_unique(acceptance, "Codex CLI не запускается без explicit user action.")
        _add_unique(acceptance, "Runner не делает commit, push, PR или deploy.")
        _add_unique(acceptance, "Все новые runner results сохраняются в task artifacts.")

    if _contains_any(lowered, MAC_MINI_KEYWORDS):
        _add_unique(categories, "mac_mini")
        _add_unique(entities, "Mac mini runtime")
        _add_unique(actions, "обновить deployment/runbook/runtime UX")
        _add_unique(current, "- Mac mini runtime требует аккуратных инструкций без раскрытия token или полного `.env`.")
        _add_unique(expected, "- Runbook/deployment flow понятен и применим к Mac mini runtime без публикации секретов.")
        _add_unique(acceptance, "Инструкции не выводят Telegram token, полный `.env` или приватные локальные значения.")

    if "кноп" in lowered or "button" in lowered:
        _add_unique(entities, "кнопки")
        _add_unique(actions, "добавить или обновить кнопки")
        _add_unique(acceptance, "Нужные кнопки отображаются в соответствующих сообщениях.")

    if "русск" in lowered or "на русском" in lowered:
        _add_unique(constraints, "Все пользовательские тексты должны быть на русском.")

    if not entities:
        entities.extend(["целевой пользовательский сценарий", "существующие project patterns"])
    if not actions:
        actions.append("внести минимальное изменение, которое прямо закрывает запрос")
    if not current:
        current.append("- Текущее поведение нужно уточнить по коду и документации перед изменениями.")
    if not expected:
        expected.append("- Поведение после изменения прямо закрывает пользовательский запрос без расширения scope.")
    if not steps:
        steps.extend(
            [
                "Прочитать project memory files и suggested files.",
                "Найти existing patterns для похожего поведения.",
                "Сформулировать минимальное изменение, которое прямо закрывает запрос.",
                "Внести scoped code/docs/tests changes без unrelated refactor.",
                "Добавить focused tests на новое поведение или regression risk.",
            ]
        )
    if not acceptance:
        acceptance.extend(
            [
                "Изменение реализует смысл пользовательского запроса.",
                "Scope минимальный, unrelated files не тронуты.",
                "Добавлены или обновлены релевантные тесты.",
            ]
        )

    constraints.extend(
        [
            "Не делать commit/push/deploy без explicit approval.",
            "Не менять `.env` и не выводить secrets/token.",
            "Не трогать unrelated files.",
        ]
    )
    out_of_scope.extend(
        [
            "Не делать commit/push.",
            "Не делать deploy.",
            "Изменения в `.env`, local runtime config и secrets.",
            "Unrelated refactor или переписывание архитектуры целиком.",
        ]
    )

    return RequirementExtraction(
        goal=goal,
        entities=entities,
        actions=actions,
        constraints=constraints,
        expected_results=expected,
        current_behavior=current,
        implementation_steps=steps,
        acceptance_criteria=acceptance,
        out_of_scope=out_of_scope,
        categories=categories,
    )


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
    extraction = extract_requirements(raw_request)
    if extraction.categories:
        return extraction.categories[0]
    return "general"


def suggested_files_for_request(raw_request: str) -> list[str]:
    extraction = extract_requirements(raw_request)
    files: list[str] = []
    category_files = {
        "telegram_ux": TELEGRAM_FILES,
        "task_card_ux": TASK_CARD_FILES,
        "project_management_ux": PROJECT_UX_FILES,
        "codex_runner": CODEX_RUNNER_FILES,
        "mac_mini": MAC_MINI_FILES,
    }
    for category in extraction.categories:
        for file in category_files.get(category, []):
            _add_unique(files, file)
    if not files:
        files.extend(BASIC_FILES)
    return files


def task_brief(raw_request: str) -> str:
    extraction = extract_requirements(raw_request)
    return (
        "Разобрать короткую задачу пользователя через Analyst Skill и внести минимальное изменение "
        f"без расширения scope: {extraction.goal}"
    )


def current_behavior_for_request(raw_request: str) -> str:
    return "\n".join(extract_requirements(raw_request).current_behavior)


def desired_behavior_for_request(raw_request: str) -> str:
    return "\n".join(extract_requirements(raw_request).expected_results)


def implementation_plan_for_request(raw_request: str) -> list[str]:
    steps = list(extract_requirements(raw_request).implementation_steps)
    for common_step in (
        "Сохранить совместимость существующих команд и callbacks, если они затронуты.",
        "Добавить или обновить focused tests для нового поведения.",
        "Запустить `.venv/bin/pytest` и `.venv/bin/python -m app.main`.",
    ):
        _add_unique(steps, common_step)
    return steps


def acceptance_criteria_for_request(raw_request: str) -> list[str]:
    criteria = list(extract_requirements(raw_request).acceptance_criteria)
    _add_unique(criteria, "Scope минимальный, unrelated files не тронуты.")
    _add_unique(criteria, "Все проверки проходят.")
    return criteria


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
    extraction = extract_requirements(raw_request)
    items = list(extraction.out_of_scope)
    if "task_card_ux" in extraction.categories:
        for item in (
            "Не реализовывать Railway dashboard.",
            "Не реализовывать полноценный Reviewer Agent.",
            "Не реализовывать Tester/QA Agent.",
            "Не запускать Codex CLI вручную.",
        ):
            _add_unique(items, item)
    if "codex_runner" not in extraction.categories:
        items.append("Изменения Codex Runner execution flow, если задача не про Runner.")
    if "mac_mini" not in extraction.categories:
        items.append("Mac mini deployment/launchd changes, если задача не про deployment.")
    return items


def requirement_extraction_section(raw_request: str) -> str:
    extraction = extract_requirements(raw_request)
    return "\n".join(
        [
            f"Цель: {extraction.goal}",
            "",
            "Затронутые сущности:",
            _bullet_list(extraction.entities),
            "",
            "Действия пользователя / системы:",
            _bullet_list(extraction.actions),
            "",
            "Ограничения из запроса и project rules:",
            _bullet_list(extraction.constraints),
            "",
            "Ожидаемый результат:",
            _bullet_list(extraction.expected_results),
        ]
    )


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
        requirement_extraction = requirement_extraction_section(intake.raw_request)
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

## Requirement extraction

{requirement_extraction}

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
