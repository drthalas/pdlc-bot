# Analyst Skill

Use this skill before building a Codex prompt. Its job is to understand the user's task without forcing it into an unrelated template.

## Method

1. Extract the main goal.
   - Preserve the user's intent and wording.
   - Do not silently replace the task with a similar previous task.

2. Identify entities.
   - Examples: tasks, projects, project cards, task cards, buttons, statuses, archive, prompts, Codex Runner, Mac mini, Railway dashboard, tests, review, commit.
   - Keep entities separate. For example, "project tasks" is not the same entity as "task card".

3. Identify actions.
   - Examples: open, show, hide, create, add, click, confirm, filter, archive, limit, run, inspect.

4. Identify constraints.
   - Examples: do not clone, do not deploy, do not modify `.env`, do not modify `config/projects.yaml`, do not commit/push without approval, do not run Codex CLI.

5. Derive current behavior.
   - Describe what is weak or missing for the extracted entities only.
   - Do not borrow current behavior from another task type.

6. Derive desired behavior.
   - Turn the user's words into concrete, observable behavior.
   - Preserve user-facing language requirements.

7. Derive acceptance criteria.
   - Make criteria checkable.
   - Include old behavior that must remain compatible.
   - Include Telegram `callback_data` constraints when buttons/callbacks are involved.

8. Derive out of scope.
   - Explicitly exclude dangerous or unrelated work.
   - Add request-specific exclusions when the user asks for a safe stub.

9. Select relevant files.
   - Pick files based on extracted entities and actions.
   - Use category hints only after extraction.

10. Define verification.
    - Prefer existing project test commands.
    - Fall back to `.venv/bin/pytest` and `.venv/bin/python -m app.main`.

## Rule

Do not use an unrelated template if the entities do not match the request. A request about project cards and project tasks must not receive task-card/archive behavior unless the user also asks for task cards or task archives.
