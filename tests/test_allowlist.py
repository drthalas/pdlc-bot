import logging

from app.telegram_bot import configure_safe_logging, is_user_allowed, parse_allowed_user_ids


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
