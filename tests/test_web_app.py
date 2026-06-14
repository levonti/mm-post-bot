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


def _csrf_from(response_text: str) -> str:
    marker = 'name="csrf" value="'
    start = response_text.index(marker) + len(marker)
    end = response_text.index('"', start)
    return response_text[start:end]


def test_login_requires_valid_token(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    response = client.get("/login?token=bad-token")

    assert response.status_code == 400
    assert "Login link is invalid or expired" in response.text


def test_login_sets_session_cookie_and_redirects(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    _login(client, ctx)

    assert "mmpost_session" in client.cookies


def test_home_requires_session(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login-required"


def test_home_renders_workspace_after_login(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/")

    assert response.status_code == 200
    assert "Composer" in response.text
    assert "Drafts" in response.text
    assert "Targets" in response.text
    assert "Audit" in response.text


def test_composer_saves_draft(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = _csrf_from(client.get("/").text)

    response = client.post(
        "/drafts",
        data={"csrf": csrf, "message": "Web draft"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/drafts"
    drafts = ctx.post_drafts.list_for_owner("alice-id")
    assert drafts[0].message == "Web draft"


def test_drafts_page_lists_saved_drafts(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Queued web post",
        message_sha256="hash",
    )

    response = client.get("/drafts")

    assert response.status_code == 200
    assert "Queued web post" in response.text
    assert "Open" in response.text


def test_draft_detail_updates_message(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Old web draft",
        message_sha256="old",
    )
    csrf = _csrf_from(client.get(f"/drafts/{draft.id}").text)

    response = client.post(
        f"/drafts/{draft.id}",
        data={"csrf": csrf, "message": "Updated web draft"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/drafts/{draft.id}"
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).message == "Updated web draft"


def test_draft_delete_marks_draft_deleted(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Delete web draft",
        message_sha256="hash",
    )
    csrf = _csrf_from(client.get(f"/drafts/{draft.id}").text)

    response = client.post(
        f"/drafts/{draft.id}/delete",
        data={"csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/drafts"
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "deleted"
