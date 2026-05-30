import logging

from app.telegram_bot import (
    CODEX_CALLBACK_ACK,
    build_codex_runner_started_message,
    configure_safe_logging,
    final_codex_status_from_response,
    is_task_running_status,
    is_user_allowed,
    parse_allowed_user_ids,
)


def test_empty_allowlist_allows_access():
    assert is_user_allowed(123, set()) is True


def test_user_id_in_allowlist_allows_access():
    allowed = parse_allowed_user_ids("123,456")

    assert is_user_allowed(123, allowed) is True


def test_user_id_not_in_allowlist_denies_access():
    allowed = parse_allowed_user_ids("123,456")

    assert is_user_allowed(789, allowed) is False


def test_configure_safe_logging_quiets_external_loggers():
    configure_safe_logging()

    for logger_name in ("httpx", "httpcore", "telegram", "telegram.ext", "apscheduler"):
        assert logging.getLogger(logger_name).getEffectiveLevel() >= logging.WARNING


def test_duplicate_run_codex_is_blocked_for_running_statuses():
    assert is_task_running_status("coding") is True
    assert is_task_running_status("codex_running") is True
    assert is_task_running_status("testing") is True
    assert is_task_running_status("prompt_ready") is False


def test_run_codex_callback_ack_and_started_message_are_fast_user_feedback():
    assert CODEX_CALLBACK_ACK == "Running Codex..."
    assert build_codex_runner_started_message("TASK-0007") == (
        "⏳ Codex Runner started for TASK-0007. This may take a while."
    )


def test_final_codex_status_from_response_marks_failures():
    assert final_codex_status_from_response("Codex finished.\nTests: passed") == "prompt_ready"
    assert final_codex_status_from_response("Working tree is dirty.\n M README.md") == "failed"
