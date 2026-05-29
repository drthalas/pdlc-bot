from app.telegram_bot import is_user_allowed, parse_allowed_user_ids


def test_empty_allowlist_allows_access():
    assert is_user_allowed(123, set()) is True


def test_user_id_in_allowlist_allows_access():
    allowed = parse_allowed_user_ids("123,456")

    assert is_user_allowed(123, allowed) is True


def test_user_id_not_in_allowlist_denies_access():
    allowed = parse_allowed_user_ids("123,456")

    assert is_user_allowed(789, allowed) is False
