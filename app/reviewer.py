from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from app.task_store import TaskRecord


REVIEW_REPORT_FILENAME = "review_report.md"
REVIEW_STATUS_APPROVED = "approved"
REVIEW_STATUS_CHANGES_REQUESTED = "changes_requested"
LARGE_DIFF_CHANGED_LINES = 500
TELEGRAM_UX_FILES = {
    "app/telegram_bot.py",
    "app/telegram_ui.py",
    "app/task_messages.py",
}
GIT_ACTION_ARTIFACTS = {
    "commit_exit_code.txt",
    "commit_hash.txt",
    "push_exit_code.txt",
    "deploy_exit_code.txt",
    "pr_url.txt",
    "pull_request_url.txt",
}
SECRET_NAME_RE = re.compile(r"(?:^|[-_.])(secret|token|key)(?:[-_.]|$)", re.IGNORECASE)


@dataclass(frozen=True)
class ReviewResult:
    task_id: str
    status: str
    summary: str
    checks: list[tuple[str, str, str]]
    warnings: list[str]
    required_fixes: list[str]
    report_path: Path


def _workspace(task: TaskRecord) -> Path:
    return Path(task.workspace_path)


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _write_text(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")


def _codex_exit_code(task: TaskRecord) -> str:
    return _read_text(_workspace(task) / "codex_exit_code.txt").strip()


def _tests_passed(test_report: str) -> bool:
    if not test_report.strip():
        return False
    exit_codes = re.findall(r"^Exit code: (\d+)$", test_report, flags=re.MULTILINE)
    if exit_codes:
        return all(code == "0" for code in exit_codes)
    lowered = test_report.lower()
    positive = any(marker in lowered for marker in ("passed", "success", "ok"))
    negative = any(marker in lowered for marker in ("failed", "failure", "error", "exit code: 1"))
    return positive and not negative


def _changed_files_from_diff(diff_text: str) -> list[str]:
    files: list[str] = []
    seen: set[str] = set()
    for line in diff_text.splitlines():
        path: str | None = None
        if line.startswith("diff --git "):
            parts = line.split()
            if len(parts) >= 4:
                path = parts[3]
        elif line.startswith("+++ b/"):
            path = line.removeprefix("+++ b/")
        elif line.startswith("--- a/"):
            path = line.removeprefix("--- a/")

        if path is None or path == "/dev/null":
            continue
        normalized = path.removeprefix("a/").removeprefix("b/").strip()
        if normalized and normalized not in seen:
            seen.add(normalized)
            files.append(normalized)
    return files


def is_sensitive_path(path: str) -> bool:
    normalized = path.strip()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    lowered = normalized.lower()
    if lowered == ".env" or lowered.startswith(".env."):
        return True
    if lowered.startswith("tasks/"):
        return True
    if lowered == "config/projects.yaml":
        return True
    if lowered.endswith(".sqlite3"):
        return True
    return SECRET_NAME_RE.search(Path(normalized).name) is not None


def _changed_line_count(diff_text: str) -> int:
    return sum(
        1
        for line in diff_text.splitlines()
        if (line.startswith("+") and not line.startswith("+++"))
        or (line.startswith("-") and not line.startswith("---"))
    )


def _git_action_artifacts(workspace: Path) -> list[str]:
    return sorted(name for name in GIT_ACTION_ARTIFACTS if (workspace / name).exists())


def _add_check(
    checks: list[tuple[str, str, str]],
    name: str,
    result: str,
    detail: str,
) -> None:
    checks.append((name, result, detail))


def _format_review_report(result: ReviewResult) -> str:
    lines = [
        f"# Review report: {result.task_id}",
        "",
        f"Status: {result.status}",
        "",
        "Summary:",
        result.summary,
        "",
        "Checks:",
    ]
    for name, status, detail in result.checks:
        lines.append(f"- {name}: {status} — {detail}")

    lines.extend(["", "Warnings:"])
    if result.warnings:
        lines.extend(f"- {warning}" for warning in result.warnings)
    else:
        lines.append("- none")

    lines.extend(["", "Required fixes:"])
    if result.required_fixes:
        lines.extend(f"- {fix}" for fix in result.required_fixes)
    else:
        lines.append("- none")

    recommendation = (
        "Ready for user review and commit."
        if result.status == REVIEW_STATUS_APPROVED
        else "Use the review report as input for `/fix TASK-ID <замечания>`."
    )
    lines.extend(["", "Recommendation:", recommendation, ""])
    return "\n".join(lines)


def run_reviewer(task: TaskRecord) -> ReviewResult:
    workspace = _workspace(task)
    workspace.mkdir(parents=True, exist_ok=True)
    report_path = workspace / REVIEW_REPORT_FILENAME
    checks: list[tuple[str, str, str]] = []
    warnings: list[str] = []
    required_fixes: list[str] = []

    exit_code = _codex_exit_code(task)
    if exit_code == "0":
        _add_check(checks, "Codex exit code", "passed", "0")
    else:
        detail = exit_code or "missing"
        _add_check(checks, "Codex exit code", "failed", detail)
        required_fixes.append(f"Codex exit code is {detail}.")

    test_report = _read_text(workspace / "test_report.md")
    if _tests_passed(test_report):
        _add_check(checks, "Tests", "passed", "test_report.md indicates success")
    else:
        _add_check(checks, "Tests", "failed", "test_report.md is missing or does not indicate success")
        required_fixes.append("Fix failing or missing tests before commit.")

    diff_text = _read_text(workspace / "diff.patch")
    changed_files = _changed_files_from_diff(diff_text)
    if diff_text.strip():
        _add_check(checks, "Diff exists", "passed", f"{len(changed_files)} changed file(s)")
    else:
        _add_check(checks, "Diff exists", "warning", "diff.patch is empty or missing")
        warnings.append("diff.patch is empty; confirm that the task required no code changes.")

    sensitive_files = [path for path in changed_files if is_sensitive_path(path)]
    if sensitive_files:
        _add_check(checks, "Sensitive files", "failed", ", ".join(sensitive_files))
        required_fixes.extend(f"Remove changes to protected file: {path}." for path in sensitive_files)
    else:
        _add_check(checks, "Sensitive files", "passed", "no protected paths in diff")

    action_artifacts = _git_action_artifacts(workspace)
    if action_artifacts:
        _add_check(checks, "Commit/push/deploy", "failed", ", ".join(action_artifacts))
        required_fixes.append("codex_run must not commit, push, create PRs, or deploy before approval.")
    else:
        _add_check(checks, "Commit/push/deploy", "passed", "no git action artifacts found")

    changed_lines = _changed_line_count(diff_text)
    if changed_lines > LARGE_DIFF_CHANGED_LINES:
        _add_check(checks, "Diff size", "warning", f"{changed_lines} changed lines")
        warnings.append(f"Large diff: {changed_lines} changed lines. Review carefully.")
    else:
        _add_check(checks, "Diff size", "passed", f"{changed_lines} changed lines")

    telegram_files = sorted(path for path in changed_files if path in TELEGRAM_UX_FILES)
    if telegram_files:
        _add_check(checks, "Telegram UX Russian text", "warning", ", ".join(telegram_files))
        warnings.append("Проверить, что пользовательские Telegram-тексты на русском.")

    status = REVIEW_STATUS_CHANGES_REQUESTED if required_fixes else REVIEW_STATUS_APPROVED
    summary = (
        "Codex completed successfully, tests passed, no sensitive files changed."
        if status == REVIEW_STATUS_APPROVED
        else "Reviewer found blocking issues that should be fixed before commit."
    )
    result = ReviewResult(
        task_id=task.task_id,
        status=status,
        summary=summary,
        checks=checks,
        warnings=warnings,
        required_fixes=required_fixes,
        report_path=report_path,
    )
    _write_text(report_path, _format_review_report(result))
    return result


def review_status_from_report(task: TaskRecord) -> str | None:
    report = _read_text(_workspace(task) / REVIEW_REPORT_FILENAME)
    match = re.search(r"^Status:\s*(\S+)\s*$", report, flags=re.MULTILINE)
    return match.group(1) if match else None


def ensure_review_report(task: TaskRecord) -> ReviewResult:
    return run_reviewer(task)


def build_review_report_message(task: TaskRecord, max_chars: int = 3500) -> str:
    report_path = _workspace(task) / REVIEW_REPORT_FILENAME
    if not report_path.exists():
        run_reviewer(task)
    report = _read_text(report_path).strip()
    if not report:
        return f"Review report для {task.task_id} не найден."
    if len(report) > max_chars:
        report = f"{report[:max_chars].rstrip()}\n\n... обрезано. Полный отчёт: {report_path}"
    return report


def format_review_result_line(status: str | None) -> str:
    if status == REVIEW_STATUS_APPROVED:
        return "✅ Review: approved"
    if status == REVIEW_STATUS_CHANGES_REQUESTED:
        return "⚠️ Review: changes requested"
    return "Review: not available"
