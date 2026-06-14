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
