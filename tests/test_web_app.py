from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from test_commands import FERNET_KEY
from test_commands import ctx as _commands_ctx
from test_commands import pg_conn as _commands_pg_conn

from mm_post_bot.config import Settings
from mm_post_bot.security import encrypt_token, hash_message
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


def _ready_target(ctx):
    ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext=encrypt_token("secret-token", FERNET_KEY),
        token_fingerprint="fp",
    )
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    ctx.user_post_defaults.set_for_owner("alice-id", bot_alias="news", channel_alias="town")


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


def test_web_uses_stored_russian_locale(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_preferences.set_locale("alice-id", "ru")
    ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Русский черновик",
        message_sha256="hash",
    )
    ctx.audits.record(
        caller_user_id="alice-id",
        caller_username="alice",
        draft_id=10,
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
    draft = ctx.post_drafts.list_for_owner("alice-id")[0]

    home = client.get("/")
    drafts = client.get("/drafts")
    targets = client.get("/targets")
    audit = client.get("/audit")
    detail = client.get(f"/drafts/{draft.id}")

    assert home.status_code == 200
    assert '<html lang="ru">' in home.text
    assert "Новый пост Mattermost" in home.text
    assert "Сохранить черновик" in home.text
    assert "Язык" in home.text

    assert drafts.status_code == 200
    assert "Сохранённые черновики" in drafts.text
    assert "Открыть" in drafts.text

    assert targets.status_code == 200
    assert "Цели публикации" in targets.text
    assert "Цель по умолчанию не выбрана." in targets.text

    assert audit.status_code == 200
    assert "Активность" in audit.text
    assert "Последние 50 записей" in audit.text

    assert detail.status_code == 200
    assert "Редактировать черновик" in detail.text
    assert "Опубликовать" in detail.text


def test_login_required_uses_default_locale(ctx, web_settings):
    ru_settings = web_settings.model_copy(update={"default_locale": "ru"})
    app = create_app(settings=ru_settings, conn=ctx.conn)
    client = TestClient(app)

    response = client.get("/login-required")

    assert response.status_code == 401
    assert '<html lang="ru">' in response.text
    assert "Требуется вход" in response.text
    assert "Откройте свежую ссылку входа из Mattermost" in response.text


def test_language_switcher_updates_shared_preference(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = _csrf_from(client.get("/").text)

    response = client.post(
        "/language",
        data={"csrf": csrf, "locale": "ru", "next": "/targets"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/targets"
    assert ctx.user_preferences.get_locale("alice-id") == "ru"
    targets = client.get("/targets")
    assert "Цели публикации" in targets.text


def test_language_switcher_rejects_unknown_locale(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = _csrf_from(client.get("/").text)

    response = client.post(
        "/language",
        data={"csrf": csrf, "locale": "de", "next": "/"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Unsupported language" in response.text
    assert ctx.user_preferences.get_locale("alice-id") is None


def test_language_switcher_sanitizes_unsafe_next(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = _csrf_from(client.get("/").text)

    response = client.post(
        "/language",
        data={"csrf": csrf, "locale": "ru", "next": "//evil.test/path"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/"
    assert ctx.user_preferences.get_locale("alice-id") == "ru"


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


def test_composer_rejects_empty_draft(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = _csrf_from(client.get("/").text)

    response = client.post(
        "/drafts",
        data={"csrf": csrf, "message": "   \n"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Draft message cannot be empty" in response.text
    assert ctx.post_drafts.list_for_owner("alice-id") == []


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


def test_draft_detail_rejects_empty_update(ctx, web_settings):
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
        data={"csrf": csrf, "message": "  "},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Draft message cannot be empty" in response.text
    stored = ctx.post_drafts.get_for_owner("alice-id", draft.id)
    assert stored.message == "Old web draft"
    assert stored.message_sha256 == "old"


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


def test_publish_draft_from_web(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    _ready_target(ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Publish from web",
        message_sha256=hash_message("Publish from web"),
    )
    csrf = _csrf_from(client.get(f"/drafts/{draft.id}").text)

    response = client.post(
        f"/drafts/{draft.id}/publish",
        data={"csrf": csrf, "bot_alias": "", "channel_alias": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/audit"
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "sent"
    assert ctx.created_posts[0]["message"] == "Publish from web"


def test_audit_page_lists_records(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.audits.record(
        caller_user_id="alice-id",
        caller_username="alice",
        draft_id=10,
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

    response = client.get("/audit")

    assert response.status_code == 200
    assert "news-bot" in response.text
    assert "post-id" in response.text
    assert "success" in response.text


def test_targets_page_lists_aliases_and_default(ctx, web_settings):
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

    response = client.get("/targets")

    assert response.status_code == 200
    assert "news-bot" in response.text
    assert "town" in response.text
    assert "Default: news -&gt; town" in response.text
    assert "@postbot !channel add-current &lt;alias&gt;" in response.text


def test_set_and_clear_default_from_targets(ctx, web_settings):
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
    csrf = _csrf_from(client.get("/targets").text)

    response = client.post(
        "/targets/default",
        data={"csrf": csrf, "bot_alias": "news", "channel_alias": "town"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert ctx.user_post_defaults.get_for_owner("alice-id").bot.alias == "news"

    csrf = _csrf_from(client.get("/targets").text)
    response = client.post(
        "/targets/default/clear",
        data={"csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert ctx.user_post_defaults.get_for_owner("alice-id") is None


def test_set_default_rejects_invalid_aliases(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = _csrf_from(client.get("/targets").text)

    response = client.post(
        "/targets/default",
        data={"csrf": csrf, "bot_alias": "missing", "channel_alias": "missing"},
        follow_redirects=False,
    )

    assert response.status_code == 400
    assert "Target aliases are invalid" in response.text
    assert ctx.user_post_defaults.get_for_owner("alice-id") is None
