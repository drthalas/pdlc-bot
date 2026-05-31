from app.orchestrator import Orchestrator
from app.project_registry import ProjectRegistry
from app.task_store import TaskStore
from app.task_workspace import TaskWorkspace


def build_orchestrator(tmp_path):
    config_path = tmp_path / "projects.yaml"
    config_path.write_text(
        """
projects:
  - name: ai-sales-assistant
    aliases:
      - sales bot
    repo_url: https://example.com/ai-sales-assistant.git
    local_path: /tmp/ai-sales-assistant
    stack:
      - Python
    context_files:
      - README.md
    test_commands:
      - pytest
    risk_level: medium
""",
        encoding="utf-8",
    )
    return Orchestrator(
        registry=ProjectRegistry(config_path),
        store=TaskStore(tmp_path / "tasks.sqlite3"),
        workspace=TaskWorkspace(tmp_path / "tasks"),
    )


def test_creates_task_with_detected_project(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout in sales bot")

    assert result.project_detected is True
    assert result.record.project_name == "ai-sales-assistant"
    assert result.record.status == "prompt_ready"
    assert result.response_text.startswith("✅ Задача создана: TASK-0001")
    assert "Проект: ai-sales-assistant" in result.response_text
    assert "Статус: prompt готов" in result.response_text
    assert "Текущий этап:" in result.response_text
    assert "- codex_prompt.md" not in result.response_text


def test_creates_task_without_detected_project(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout")

    assert result.project_detected is False
    assert result.record.project_name is None
    assert result.response_text.startswith("⚠️ Задача создана: TASK-0001")
    assert "Проект: не определён" in result.response_text
    assert "В следующий раз укажи название проекта или alias из /projects." in result.response_text


def test_creates_artifacts(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("Fix checkout in ai sales assistant")
    task_path = tmp_path / "tasks" / result.record.task_id

    assert (task_path / "input.md").exists()
    assert (task_path / "project.json").exists()
    assert (task_path / "analysis.md").exists()
    assert (task_path / "implementation_plan.md").exists()
    assert (task_path / "codex_prompt.md").exists()


def test_codex_prompt_contains_project_context_files_and_rules(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant улучши Telegram UX")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    for filename in (
        "docs/PROMPT_BUILDER.md",
        "PROJECT_CONTEXT.md",
        "TASKS.md",
        "DECISIONS.md",
        "README.md",
        "docs/ROADMAP.md",
        "docs/CODEX_RUNNER_V0.md",
    ):
        assert filename in prompt
    assert "Relevant docs/*.md files for the task topic" in prompt
    assert "Все пользовательские Telegram-тексты должны быть на русском по умолчанию." in prompt
    assert "Technical artifact filenames, internal status values и code identifiers могут оставаться на английском." in prompt
    assert "Codex Runner не должен делать commit, push или deploy без явного approval." in prompt
    assert "Mac mini — execution runtime." in prompt
    assert "Railway dashboard / PDLC Control Center запланирован позже." in prompt
    assert "Tester/QA Agent обязателен в future roadmap." in prompt
    assert "scope минимальным и не трогай unrelated files" in prompt


def test_codex_prompt_includes_mac_mini_runbook_for_deployment_tasks(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant обнови Mac mini deployment runbook")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    assert "docs/MAC_MINI_RUNBOOK.md" in prompt


def test_codex_prompt_follows_prompt_builder_structure(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant улучши Telegram UX списка задач")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    for heading in (
        "# Ты Codex, работаешь над TASK-0001",
        "## Target project",
        "## User request",
        "## Project memory / context",
        "## Permanent project rules",
        "## Task brief",
        "## Current behavior",
        "## Desired behavior",
        "## Suggested files to inspect",
        "## Implementation plan",
        "## Acceptance criteria",
        "## Safety constraints",
        "## Out of scope",
        "## Verification",
        "## Report format",
    ):
        assert heading in prompt


def test_codex_prompt_for_russian_task_is_mostly_russian(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant добавь русские кнопки в Telegram меню")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    for phrase in (
        "Перед изменениями прочитай",
        "Пользователь должен видеть понятный русский Telegram UX",
        "Пользовательские Telegram-тексты на русском",
        "Нужные кнопки/пункты меню отображаются",
    ):
        assert phrase in prompt


def test_codex_prompt_for_telegram_task_has_specific_files_and_acceptance_criteria(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant улучши Telegram кнопки и callbacks")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    for filename in (
        "app/telegram_ui.py",
        "app/telegram_bot.py",
        "tests/test_telegram_ui.py",
        "app/task_messages.py",
    ):
        assert filename in prompt
    assert "callback_data для inline-кнопок не превышает 64 bytes" in prompt
    assert "Старые команды `/start`, `/projects`, `/status`, `/tasks`, `/task`, `/prompt` не сломаны" in prompt
    assert "Добавлены или обновлены focused tests" in prompt


def test_codex_prompt_contains_safety_out_of_scope_and_verification(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task("В ai-sales-assistant добавь новую кнопку в Telegram меню")
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    assert "## Safety constraints" in prompt
    assert "Не запускать Telegram polling/API" in prompt
    assert "Не делать commit, push, PR или deploy без explicit approval." in prompt
    assert "## Out of scope" in prompt
    assert "Unrelated refactor" in prompt
    assert "## Verification" in prompt
    assert "`pytest`" in prompt
    assert "`.venv/bin/python -m app.main`" in prompt


def test_codex_prompt_for_task_card_request_has_concrete_decomposition(tmp_path):
    orchestrator = build_orchestrator(tmp_path)

    result = orchestrator.create_task(
        "В ai-sales-assistant сделай нормальную карточку задачи: чтобы было видно название, проект, "
        "текущий этап, что уже выполнено и какие действия доступны дальше. Технические файлы спрячь "
        "в отдельную кнопку. В списке задач показывай только последние 10, старые вынеси в архив. "
        "Все пользовательские тексты — на русском."
    )
    prompt = (tmp_path / "tasks" / result.record.task_id / "codex_prompt.md").read_text(encoding="utf-8")

    for phrase in (
        "`/task TASK-ID` показывает слишком много технической информации и artifacts.",
        "Пользователю сложно понять текущий этап задачи.",
        "В карточке задачи не видно прогресс: prompt, Codex, tests, review, commit.",
        "`/tasks` и Recent tasks недостаточно понятно показывают, о чём задача.",
        "Основной список задач может разрастаться.",
        "Старые задачи не вынесены в архив.",
        "Технические файлы не должны показываться по умолчанию.",
    ):
        assert phrase in prompt

    for phrase in (
        "Карточка задачи показывает TASK-ID, название, проект, текущий статус и текущий этап.",
        "Карточка показывает прогресс: задача создана, prompt готов, Codex выполнен или нет",
        "Технические artifacts скрыты за кнопкой `🛠 Технические детали`.",
        "`/tasks` показывает максимум 10 последних задач.",
        "Старые задачи доступны через `📦 Архив задач`.",
        "Задачи в списке показываются с коротким названием из `input.md`.",
        "Все пользовательские Telegram-тексты на русском.",
        "Кнопки зависят от текущего состояния задачи.",
    ):
        assert phrase in prompt

    for filename in (
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
    ):
        assert filename in prompt

    for phrase in (
        "Найти, где формируется `/task TASK-ID` и Task details callback.",
        "Скрыть raw artifact list из карточки задачи.",
        "Добавить кнопку `🛠 Технические детали` и отдельный callback для artifacts.",
        "Обновить `/tasks` и Recent tasks: максимум 10 задач.",
        "Добавить `📦 Архив задач` для старых задач.",
        "Убедиться, что post-run задачи не показывают `▶️ Запустить Codex` как основное действие.",
    ):
        assert phrase in prompt

    for phrase in (
        "`/task TASK-ID` не показывает raw artifacts по умолчанию.",
        "Карточка задачи содержит название, проект, статус, текущий этап и progress checklist.",
        "Technical details callback показывает artifacts отдельно.",
        "`/tasks` показывает максимум 10 последних задач.",
        "Если задач больше 10, есть кнопка `📦 Архив задач`.",
        "Task title берётся из `input.md`.",
        "Длинный title обрезается до 60–80 символов.",
        "Missing `input.md` даёт fallback на `TASK-ID`.",
        "Post-run task показывает diff/tests/review/commit/discard, а не `▶️ Запустить Codex`.",
        "Callback data не длиннее 64 символов.",
        "Старые команды не сломаны.",
    ):
        assert phrase in prompt

    for phrase in (
        "Не реализовывать Railway dashboard.",
        "Не реализовывать полноценный Reviewer Agent.",
        "Не реализовывать Tester/QA Agent.",
        "Не делать deploy.",
        "Не делать commit/push.",
        "Не менять `.env`",
        "Не запускать Codex CLI вручную.",
        "Unrelated refactor",
    ):
        assert phrase in prompt
