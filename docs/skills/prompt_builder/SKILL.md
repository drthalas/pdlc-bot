# Prompt Builder Skill

Use this skill after Analyst Skill has extracted requirements from the user's request.

## Prompt Assembly

Build `codex_prompt.md` with these sections:

1. `Ты Codex, работаешь над TASK-XXXX`
2. `Target project`
3. `User request`
4. `Project memory / context`
5. `Permanent project rules`
6. `Task brief`
7. `Requirement extraction`
   - goal
   - affected entities
   - actions
   - constraints
   - expected result
8. `Current behavior`
9. `Desired behavior`
10. `Suggested files to inspect`
11. `Implementation plan`
12. `Acceptance criteria`
13. `Safety constraints`
14. `Out of scope`
15. `Verification`
16. `Report format`

## Rules

- The prompt should be mostly Russian when the user request is Russian.
- Technical artifact filenames, internal statuses, file paths, callback identifiers, and code identifiers may remain English.
- Project memory and permanent rules must appear before implementation instructions.
- Current behavior, desired behavior, plan, and acceptance criteria must come from Analyst Skill extraction.
- Category hints can add relevant files and checks, but they must not replace the extracted requirements.
- The prompt must clearly state that commit, push, deploy, secret changes, Telegram polling, and real Codex execution require explicit approval when relevant.
