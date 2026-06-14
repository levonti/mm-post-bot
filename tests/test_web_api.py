from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_commands import FERNET_KEY
from test_commands import ctx as _commands_ctx
from test_commands import pg_conn as _commands_pg_conn

from mm_post_bot.config import Settings
from mm_post_bot.services.web_auth import create_login_token, hash_login_token
from mm_post_bot.web.app import create_app

ctx = _commands_ctx
pg_conn = _commands_pg_conn


@pytest.fixture()
def web_settings():
    return Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=FERNET_KEY,
        web_base_url="https://posts.internal",
        web_session_secret="s" * 32,
    )


def _login(client: TestClient, ctx) -> None:
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    raw = create_login_token(
        token_repo=ctx.web_login_tokens,
        owner_user_id="alice-id",
        now=datetime.now(UTC),
        ttl_seconds=300,
    )
    response = client.get(f"/login?token={raw}", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert ctx.web_login_tokens.get_usable(hash_login_token(raw), now=datetime.now(UTC)) is None


def test_api_bootstrap_returns_session_csrf_locale_and_nav(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/api/web/bootstrap")

    assert response.status_code == 200
    body = response.json()
    assert body["session"] == {"user_id": "alice-id", "username": "alice"}
    assert body["locale"] == "en"
    assert body["csrf"]
    assert body["nav"] == [
        {"href": "/", "key": "composer", "label": "Composer"},
        {"href": "/drafts", "key": "drafts", "label": "Drafts"},
        {"href": "/targets", "key": "targets", "label": "Targets"},
        {"href": "/audit", "key": "audit", "label": "Audit"},
    ]


def test_api_targets_returns_bots_channels_default_and_csrf(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher",
        token_fingerprint="fp",
    )
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    ctx.user_post_defaults.set_for_owner("alice-id", bot_alias="news", channel_alias="town")

    response = client.get("/api/web/targets")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["bots"][0]) == {
        "alias",
        "bot_user_id",
        "bot_username",
        "bot_display_name",
    }
    assert payload["bots"][0]["alias"] == "news"
    assert payload["bots"][0]["bot_user_id"] == "bot-id"
    assert payload["bots"][0]["bot_username"] == "news-bot"
    assert "token_ciphertext" not in payload["bots"][0]
    assert "token_fingerprint" not in payload["bots"][0]
    assert set(payload["channels"][0]) == {
        "alias",
        "channel_id",
        "created_at",
        "updated_at",
    }
    assert payload["channels"][0]["alias"] == "town"
    assert payload["channels"][0]["channel_id"] == "channel-id"
    assert payload["default"] == {"bot_alias": "news", "channel_alias": "town"}
    assert payload["stale_default"] is False
    assert payload["csrf"]


def test_api_targets_reports_stale_default(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher",
        token_fingerprint="fp",
    )
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    ctx.user_post_defaults.set_for_owner("alice-id", bot_alias="news", channel_alias="town")
    ctx.user_channels.soft_delete("alice-id", "town")

    response = client.get("/api/web/targets")

    assert response.status_code == 200
    payload = response.json()
    assert payload["default"] is None
    assert payload["stale_default"] is True


def test_api_drafts_returns_drafts(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Hello from API",
        message_sha256="hash",
    )

    response = client.get("/api/web/drafts")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["drafts"][0]) == {
        "id",
        "message",
        "message_sha256",
        "status",
        "created_at",
        "updated_at",
        "sent_at",
        "sent_by_user_bot_id",
        "sent_channel_id",
        "mattermost_post_id",
    }
    assert payload["drafts"][0]["id"] == draft.id
    assert payload["drafts"][0]["message"] == "Hello from API"
    assert payload["drafts"][0]["status"] == "draft"
    assert payload["csrf"]


def test_api_audit_returns_records(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.audits.record(
        caller_user_id="alice-id",
        caller_username="alice",
        draft_id=None,
        user_bot_id=None,
        bot_user_id="bot-id",
        bot_username="news-bot",
        channel_link="town",
        resolved_channel_id="channel-id",
        resolved_team_name=None,
        resolved_channel_name=None,
        message_sha256="hash",
        status="success",
        mattermost_post_id="post-id",
        error_code=None,
        error_message=None,
    )

    response = client.get("/api/web/audit")

    assert response.status_code == 200
    payload = response.json()
    assert set(payload["records"][0]) == {
        "id",
        "caller_user_id",
        "caller_username",
        "draft_id",
        "user_bot_id",
        "bot_user_id",
        "bot_username",
        "channel_link",
        "resolved_channel_id",
        "resolved_team_name",
        "resolved_channel_name",
        "message_sha256",
        "status",
        "mattermost_post_id",
        "error_code",
        "error_message",
        "created_at",
    }
    assert payload["records"][0]["mattermost_post_id"] == "post-id"
    assert payload["records"][0]["status"] == "success"
    assert payload["records"][0]["resolved_channel_id"] == "channel-id"
    assert payload["csrf"]
