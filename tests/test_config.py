from mm_post_bot.config import Settings


def test_settings_parse_admins_and_urls():
    settings = Settings(
        mm_url="https://mm.internal/i",
        mm_bot_token="manager-token",
        mm_admins="alice, bob",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key="0" * 44,
    )

    assert settings.admin_usernames == ["alice", "bob"]
    assert settings.mm_rest_base == "https://mm.internal/i/api/v4"
    assert settings.mm_ws_url == "wss://mm.internal/i/api/v4/websocket"


def test_settings_have_no_system_admin_token_field():
    assert "mm_token" not in Settings.model_fields
