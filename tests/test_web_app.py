import subprocess
import sys
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


def _spa_web_dir(tmp_path):
    spa_assets = tmp_path / "static" / "spa" / "assets"
    spa_assets.mkdir(parents=True)
    (tmp_path / "static" / "spa" / "index.html").write_text(
        '<div id="root"></div><script src="/assets/preview.js"></script>',
        encoding="utf-8",
    )
    (spa_assets / "preview.js").write_text("console.log('preview');", encoding="utf-8")
    return tmp_path


def test_login_requires_valid_token(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    response = client.get("/login?token=bad-token")

    assert response.status_code == 400
    assert "Login link is invalid or expired" in response.text


def test_web_entrypoint_imports_without_command_cycle():
    result = subprocess.run(
        [sys.executable, "-c", "import mm_post_bot.web.__main__"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr


def test_login_sets_session_cookie_and_redirects(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    _login(client, ctx)

    assert "mmpost_session" in client.cookies


def test_logout_clears_session_cookie(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post("/api/web/logout", data={"csrf": csrf})

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert "mmpost_session" not in client.cookies


def test_home_requires_session(ctx, web_settings, tmp_path):
    app = create_app(settings=web_settings, conn=ctx.conn, web_dir=_spa_web_dir(tmp_path))
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login-required"


def test_home_serves_react_app_after_login(ctx, web_settings, tmp_path):
    app = create_app(settings=web_settings, conn=ctx.conn, web_dir=_spa_web_dir(tmp_path))
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/")

    assert response.status_code == 200
    assert '<div id="root"></div>' in response.text


def test_login_required_uses_default_locale_without_jinja(ctx, web_settings):
    ru_settings = web_settings.model_copy(update={"default_locale": "ru"})
    app = create_app(settings=ru_settings, conn=ctx.conn)
    client = TestClient(app)

    response = client.get("/login-required")

    assert response.status_code == 401
    assert '<html lang="ru">' in response.text
    assert "Требуется вход" in response.text
    assert "Откройте свежую ссылку входа из Mattermost" in response.text


def test_app_starts_when_built_static_dir_is_missing(ctx, web_settings, tmp_path):
    app = create_app(settings=web_settings, conn=ctx.conn, web_dir=tmp_path)
    client = TestClient(app)

    response = client.get("/login-required")

    assert response.status_code == 401
    assert "Login required" in response.text


def test_react_routes_serve_spa_shell(ctx, web_settings, tmp_path):
    app = create_app(settings=web_settings, conn=ctx.conn, web_dir=_spa_web_dir(tmp_path))
    client = TestClient(app)
    _login(client, ctx)

    for path in ("/", "/drafts", "/drafts/123", "/targets", "/audit", "/app/drafts/123"):
        response = client.get(path)
        assert response.status_code == 200
        assert '<div id="root"></div>' in response.text

    asset_response = client.get("/assets/preview.js")
    assert asset_response.status_code == 200
    assert "console.log('preview');" in asset_response.text

    preview_asset_response = client.get("/app/assets/preview.js")
    assert preview_asset_response.status_code == 200
    assert "console.log('preview');" in preview_asset_response.text


def test_legacy_jinja_routes_are_removed(ctx, web_settings, tmp_path):
    app = create_app(settings=web_settings, conn=ctx.conn, web_dir=_spa_web_dir(tmp_path))
    client = TestClient(app)
    _login(client, ctx)

    for path in ("/legacy", "/legacy/drafts", "/legacy/targets", "/legacy/audit"):
        response = client.get(path)
        assert response.status_code == 404


def test_legacy_static_assets_are_removed(ctx, web_settings, tmp_path):
    app = create_app(settings=web_settings, conn=ctx.conn, web_dir=_spa_web_dir(tmp_path))
    client = TestClient(app)

    assert client.get("/static/app.css").status_code == 404
    assert client.get("/static/app.js").status_code == 404
