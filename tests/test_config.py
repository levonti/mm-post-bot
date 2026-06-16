import pytest
from pydantic import ValidationError

from mm_post_bot.config import Settings

VALID_FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="
VALID_WEB_SESSION_SECRET = "x" * 32


def test_settings_parse_admins_and_urls():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice, bob",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        web_session_secret=VALID_WEB_SESSION_SECRET,
    )

    assert settings.admin_usernames == ["alice", "bob"]
    assert settings.mm_rest_base == "https://mm.internal/api/v4"
    assert settings.mm_ws_url == "wss://mm.internal/api/v4/websocket"


def test_settings_have_no_system_admin_token_field():
    assert "mm_token" not in Settings.model_fields


def test_settings_default_locale_defaults_to_english():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        web_session_secret=VALID_WEB_SESSION_SECRET,
    )

    assert settings.default_locale == "en"


def test_settings_normalize_default_locale():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        web_session_secret=VALID_WEB_SESSION_SECRET,
        default_locale=" RU ",
    )

    assert settings.default_locale == "ru"


def test_settings_reject_unknown_default_locale():
    with pytest.raises(ValidationError, match="DEFAULT_LOCALE must be one of: en, ru"):
        Settings(
            mm_url="https://mm.internal",
            mm_bot_token="manager-token",
            mm_admins="alice",
            db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
            token_encryption_key=VALID_FERNET_KEY,
            web_session_secret=VALID_WEB_SESSION_SECRET,
            default_locale="fr",
        )


def test_settings_normalize_admin_mentions():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="@alice, @bob",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        web_session_secret=VALID_WEB_SESSION_SECRET,
    )

    assert settings.admin_usernames == ["alice", "bob"]


def test_settings_reject_invalid_token_encryption_key():
    with pytest.raises(ValidationError, match="TOKEN_ENCRYPTION_KEY must be a valid Fernet key"):
        Settings(
            mm_url="https://mm.internal",
            mm_bot_token="manager-token",
            mm_admins="alice",
            db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
            token_encryption_key="too-short",
            web_session_secret=VALID_WEB_SESSION_SECRET,
        )


def test_settings_do_not_echo_invalid_token_encryption_key():
    invalid_key = "not-a-real-secret-key"

    with pytest.raises(ValidationError) as exc_info:
        Settings(
            mm_url="https://mm.internal",
            mm_bot_token="manager-token",
            mm_admins="alice",
            db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
            token_encryption_key=invalid_key,
            web_session_secret=VALID_WEB_SESSION_SECRET,
        )

    assert invalid_key not in str(exc_info.value)


def test_web_settings_defaults_are_local_safe():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        web_base_url="http://localhost:8080",
        web_session_secret="x" * 32,
    )

    assert str(settings.web_base_url).rstrip("/") == "http://localhost:8080"
    assert settings.web_host == "0.0.0.0"
    assert settings.web_port == 8080
    assert settings.web_cookie_secure is False
    assert settings.web_login_token_ttl_seconds == 300
    assert settings.web_session_max_age_seconds == 7 * 24 * 60 * 60


def test_web_session_secret_requires_length():
    try:
        Settings(
            mm_url="https://mm.internal",
            mm_bot_token="manager-token",
            mm_admins="alice",
            db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
            token_encryption_key=VALID_FERNET_KEY,
            web_base_url="http://localhost:8080",
            web_session_secret="short",
        )
    except ValueError as exc:
        assert "WEB_SESSION_SECRET must be at least 32 characters" in str(exc)
    else:
        raise AssertionError("short web session secret should be rejected")
