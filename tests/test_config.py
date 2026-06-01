import pytest
from pydantic import ValidationError

from mm_post_bot.config import Settings

VALID_FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


def test_settings_parse_admins_and_urls():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice, bob",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
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
    )

    assert settings.default_locale == "en"


def test_settings_normalize_default_locale():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
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
            default_locale="fr",
        )


def test_settings_normalize_admin_mentions():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="@alice, @bob",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
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
        )

    assert invalid_key not in str(exc_info.value)
