# Prompt Builder

`pdlc-bot` turns short Telegram task requests into structured Codex prompts. The goal is to give Codex enough project context, task-specific detail, safety constraints, and verification guidance without requiring the user to paste a large manual prompt.

Prompts should be mostly Russian when the user's request is Russian. Technical artifact filenames, internal status values, file paths, callback identifiers, and code identifiers may remain English.

## Codex Prompt Structure

Every generated `codex_prompt.md` should follow this structure:

1. `Ты Codex, работаешь над TASK-XXXX`
2. `Target project`
   - project name
   - `repo_url`
   - `local_path`
3. `User request`
   - the original user request without changing its meaning
4. `Project memory / context`
   - `PROJECT_CONTEXT.md`
   - `TASKS.md`
   - `DECISIONS.md`
   - `README.md`
   - `docs/ROADMAP.md`
   - `docs/CODEX_RUNNER_V0.md`
   - relevant `docs/*.md`
   - `docs/MAC_MINI_RUNBOOK.md` when the task mentions Mac mini, deployment, launchd, service operations, or runbooks
5. `Permanent project rules`
   - all Telegram user-facing text should be Russian by default
   - technical artifact filenames, internal statuses, and code identifiers may remain English
   - Codex Runner must not commit, push, or deploy without explicit approval
   - Mac mini is the execution runtime
   - Railway dashboard / PDLC Control Center is planned later
   - Tester/QA Agent is mandatory in the future roadmap
   - keep scope minimal and do not touch unrelated files
6. `Task brief`
   - a short task-specific summary
7. `Requirement extraction`
   - goal
   - affected entities
   - actions
   - constraints
   - expected result
8. `Current behavior`
   - what is currently wrong, weak, or inconvenient
9. `Desired behavior`
   - what should be true after the change
10. `Suggested files to inspect`
   - concrete files selected for the task topic
11. `Implementation plan`
   - 5-10 concrete steps for this task
12. `Acceptance criteria`
   - specific, testable checks
13. `Safety constraints`
   - what must not be done
14. `Out of scope`
   - what should explicitly not be implemented now
15. `Verification`
   - concrete commands to run
16. `Report format`
   - what Codex should report back

## Generic Task Decomposition

Prompt Builder must first build requirement extraction, then assemble the prompt. It should not select a rigid task template first.

Requirement extraction includes:

- goal
- affected entities
- user/system actions
- constraints
- expected result

Category hints such as Telegram UX, Codex Runner, Project management, Mac mini/deployment, and docs may add relevant files and safety checks. They must not override the extracted entities. If a request mentions "задачи проекта", the entity is project tasks, not automatically task cards or task archive.

Project UX and task UX must stay separate:

- "карточка проекта", "карточку проекта", "GitHub URL", "repo_url", "local_path", "описание проекта", and "задачи проекта" are project-management entities.
- "карточка задачи", "TASK-ID", "этап задачи", and progress across prompt/Codex/tests/review/commit are task-card entities.
- A project-management request must not receive task-card current behavior, task progress checklist, or archive behavior unless the user explicitly asks for task cards, task lists, or task archives.
- A phrase like "задачами проекта" means tasks filtered by project, not a generic task card.

The detailed method is documented in [docs/skills/analyst/SKILL.md](skills/analyst/SKILL.md), and prompt assembly is documented in [docs/skills/prompt_builder/SKILL.md](skills/prompt_builder/SKILL.md).

## Topic-Specific File Selection

For Telegram UX tasks, include files such as:

- `app/telegram_bot.py`
- `app/telegram_ui.py`
- `app/task_messages.py`
- `app/task_store.py`
- `app/post_run_controls.py`
- `tests/test_telegram_ui.py`
- `tests/test_task_messages.py`

For project management UX tasks, include files such as:

- `app/telegram_bot.py`
- `app/telegram_ui.py`
- `app/project_registry.py`
- `app/task_store.py`
- `config/projects.example.yaml`
- `tests/test_telegram_ui.py`
- `tests/test_project_registry.py`
- `tests/test_task_store.py`
- `README.md`

For Codex Runner tasks, include files such as:

- `app/codex_runner.py`
- `app/post_run_controls.py`
- `docs/CODEX_RUNNER_V0.md`
- `tests/test_codex_runner.py`
- `tests/test_post_run_controls.py`

For Mac mini, deployment, launchd, service, or runbook tasks, include files such as:

- `docs/MAC_MINI_RUNBOOK.md`
- `README.md`
- `docs/ROADMAP.md`

When the task type is unclear, start with:

- `README.md`
- `PROJECT_CONTEXT.md`
- `TASKS.md`
- `DECISIONS.md`

## Task-Specific Decomposition

Prompt Builder should not simply repeat a generic plan. It should decompose the user's short request into concrete requirements by looking for nouns, verbs, limits, UI labels, safety words, and explicit exclusions.

For Russian Telegram UX requests:

- preserve the original meaning of the user's wording
- extract visible UI objects, such as task card, task list, archive, buttons, menus, and callbacks
- extract limits, such as "последние 10" or "60-80 символов"
- convert vague UX goals into checkable behavior
- keep technical identifiers and artifact filenames in English when that matches the codebase
- keep user-facing Telegram text in Russian

For task card, task list, and archive requests, Prompt Builder should produce concrete sections instead of a generic "inspect files" plan.

### Example: Task Card / Recent Tasks / Archive

User request:

```text
В pdlc-bot сделай нормальную карточку задачи: чтобы было видно название, проект, текущий этап, что уже выполнено и какие действия доступны дальше. Технические файлы спрячь в отдельную кнопку. В списке задач показывай только последние 10, старые вынеси в архив. Все пользовательские тексты — на русском.
```

Expected `Current behavior` should mention:

- `/task TASK-ID` shows too much technical information and artifacts
- the user cannot easily understand the current task stage
- the task card does not show progress across prompt, Codex, tests, review, and commit
- `/tasks` and Recent tasks do not clearly show what each task is about
- the main task list can grow indefinitely
- old tasks are not moved behind an archive action
- technical files should not be shown by default

Expected `Desired behavior` should mention:

- the task card shows TASK-ID, title, project, status, and current stage
- the task card shows progress for created, prompt ready, Codex done, tests, review, and commit
- technical artifacts are hidden behind `🛠 Технические детали`
- `/tasks` shows at most 10 recent tasks
- older tasks are available through `📦 Архив задач`
- tasks are listed with short titles from `input.md`
- all user-facing Telegram text is Russian
- buttons depend on the current task state

Expected `Suggested files to inspect` should include:

- `app/telegram_bot.py`
- `app/telegram_ui.py`
- `app/task_messages.py`
- `app/task_store.py`
- `app/post_run_controls.py`
- `tests/test_telegram_ui.py`
- `tests/test_task_messages.py`
- `README.md`
- `docs/CODEX_RUNNER_V0.md`
- `DECISIONS.md`

Expected implementation plan should include concrete steps:

1. Find where `/task TASK-ID` and the Task details callback are formatted.
2. Add or update a helper for a user-friendly task card.
3. Add display-state detection based on task status and artifacts.
4. Hide the raw artifact list from the default task card.
5. Add `🛠 Технические детали` and a callback that shows artifacts separately.
6. Limit `/tasks` and Recent tasks to 10 recent tasks.
7. Add `📦 Архив задач` for older tasks.
8. Use task title extraction from `input.md`.
9. Ensure post-run tasks do not show `▶️ Запустить Codex` as the primary action.
10. Update tests and documentation.

Expected acceptance criteria should be specific:

- `/task TASK-ID` does not show raw artifacts by default
- the task card contains title, project, status, current stage, and progress checklist
- `🛠 Технические детали` exists
- the technical-details callback shows artifacts separately
- `/tasks` shows at most 10 recent tasks
- when there are more than 10 tasks, `📦 Архив задач` is available
- archive shows older tasks
- task title comes from `input.md`
- long title is truncated to 60-80 characters
- missing `input.md` falls back to `TASK-ID`
- post-run tasks show diff/tests/review/commit/discard instead of `▶️ Запустить Codex`
- all user-facing Telegram text is Russian
- callback data stays within 64 bytes
- old slash commands still work

### Example: Project Management UX

User request:

```text
В pdlc-bot улучши раздел Проекты: сделай карточки проектов с описанием, GitHub URL, задачами проекта и кнопкой Добавить проект.
```

This should not be treated as task-card/archive UX just because the request mentions project tasks. It should use `project_management_ux` decomposition.

Expected `Current behavior` should mention:

- `/projects` is too flat
- project list lacks description, GitHub URL, status, and task counts
- project details are not a rich project card
- there is no quick way to open tasks for a specific project
- there is no `Добавить проект` action even as a safe stub

Expected `Desired behavior` should mention:

- `/projects` shows project description, GitHub URL, status, and task count
- projects are clickable
- project card shows aliases, stack, GitHub URL, local path/status, and recent tasks for that project
- buttons include `Задачи проекта`, `Назад к проектам`, and `Добавить проект`
- `Добавить проект` is a stub and does not clone repositories or change config
- all user-facing Telegram text is Russian

Expected acceptance criteria should include:

- `/projects` shows projects with description, GitHub URL, status, and task count
- project card shows description, aliases, stack, `repo_url`, `local_path`, and status
- project card shows only tasks for that project
- `Добавить проект` does not clone and does not modify `config/projects.yaml`
- callback data stays within 64 bytes
- existing `/projects` behavior remains compatible

## Acceptance Criteria Guidance

Telegram UX prompts should ask Codex to verify that:

- user-facing Telegram text is Russian
- required buttons are shown
- `callback_data` stays within Telegram's 64-byte limit
- old slash commands still work
- tests are added or updated

Codex Runner prompts should ask Codex to verify that:

- Codex is not run without explicit user action
- commit, push, PR, and deploy are not performed
- artifacts are saved
- subprocess behavior is tested through mocks
- safety checks are preserved

## Safety

Prompt Builder must keep generated prompts explicit about boundaries. Unless a user separately approves it, Codex must not run Telegram polling, run real Codex CLI, execute `run_codex.sh`, commit, push, deploy, alter `.env`, expose tokens, or modify unrelated files.
