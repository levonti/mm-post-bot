from datetime import UTC, datetime
from typing import ClassVar

import pytest
from fastapi.testclient import TestClient
from test_commands import FERNET_KEY
from test_commands import ctx as _commands_ctx
from test_commands import pg_conn as _commands_pg_conn

from mm_post_bot.config import Settings
from mm_post_bot.mm_client import MattermostError
from mm_post_bot.security import encrypt_token
from mm_post_bot.services.web_auth import create_login_token, hash_login_token
from mm_post_bot.web import api as web_api
from mm_post_bot.web.app import create_app

ctx = _commands_ctx
pg_conn = _commands_pg_conn


class FakeChannelSearchMM:
    instances: ClassVar[list[FakeChannelSearchMM]] = []
    teams: ClassVar[list[dict[str, str]]] = [{"id": "team-id", "name": "demo"}]
    results_by_term: ClassVar[dict[str, list[dict[str, str]]]] = {
        "town": [
            {
                "id": "town-channel-id",
                "name": "town-square",
                "display_name": "Town Square",
                "type": "O",
                "team_id": "team-id",
            }
        ]
    }
    channels_by_id: ClassVar[dict[str, dict[str, str]]] = {
        "channel-id": {
            "id": "channel-id",
            "name": "town-square",
            "display_name": "Town Square",
            "team_id": "team-id",
        }
    }

    def __init__(
        self,
        rest_base: str,
        token: str,
        *,
        timeout: float = 15.0,
        verify_ssl: bool = True,
    ) -> None:
        self.rest_base = rest_base
        self.token = token
        self.timeout = timeout
        self.verify_ssl = verify_ssl
        self.closed = False
        FakeChannelSearchMM.instances.append(self)

    async def get_my_teams(self) -> list[dict[str, str]]:
        return self.teams

    async def search_channels(self, team_id: str, term: str) -> list[dict[str, str]]:
        assert team_id == "team-id"
        return self.results_by_term.get(term, [])

    async def get_channel(self, channel_id: str) -> dict[str, str]:
        return self.channels_by_id[channel_id]

    async def aclose(self) -> None:
        self.closed = True


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


def test_api_targets_returns_bots_channels_default_and_csrf(ctx, web_settings, monkeypatch):
    monkeypatch.setattr(web_api, "MattermostClient", FakeChannelSearchMM)
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
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
        "display_name",
        "team_name",
        "updated_at",
    }
    assert payload["channels"][0]["alias"] == "town"
    assert payload["channels"][0]["channel_id"] == "channel-id"
    assert payload["channels"][0]["display_name"] == "Town Square"
    assert payload["channels"][0]["team_name"] == "demo"
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
        token_ciphertext=encrypt_token("secret-token", FERNET_KEY),
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


def test_api_targets_renames_channel_alias(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/channels/town/rename",
        data={"csrf": csrf, "new_alias": "announcements"},
    )

    assert response.status_code == 200
    assert response.json()["alias"] == "announcements"
    assert (
        ctx.user_channels.get_by_owner_and_alias("alice-id", "announcements").channel_id
        == "channel-id"
    )


def test_api_targets_rejects_blank_channel_alias_rename(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/channels/town/rename",
        data={"csrf": csrf, "new_alias": "  "},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Choose a channel and enter an alias."}
    assert ctx.user_channels.get_by_owner_and_alias("alice-id", "town").channel_id == "channel-id"


def test_api_targets_rejects_duplicate_channel_alias_rename(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="town-id")
    ctx.user_channels.add(owner_user_id="alice-id", alias="alerts", channel_id="alerts-id")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/channels/town/rename",
        data={"csrf": csrf, "new_alias": "alerts"},
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Channel alias already exists"}
    assert ctx.user_channels.get_by_owner_and_alias("alice-id", "town").channel_id == "town-id"


def test_api_targets_deletes_channel_alias(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/channels/town/delete",
        data={"csrf": csrf},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    with pytest.raises(LookupError):
        ctx.user_channels.get_by_owner_and_alias("alice-id", "town")


def test_api_targets_channel_search_returns_results(ctx, web_settings, monkeypatch):
    monkeypatch.setattr(web_api, "MattermostClient", FakeChannelSearchMM)
    FakeChannelSearchMM.instances.clear()
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/api/web/targets/channels/search?q=town")

    assert response.status_code == 200
    assert response.json() == {
        "results": [
            {
                "id": "town-channel-id",
                "name": "town-square",
                "display_name": "Town Square",
                "team_name": "demo",
                "label": "Town Square (demo/town-square)",
            }
        ]
    }
    assert FakeChannelSearchMM.instances[0].closed is True


def test_api_targets_adds_channel_from_search_result(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/channels",
        data={
            "csrf": csrf,
            "channel_alias": "town",
            "channel_id": "town-channel-id",
            "channel_label": "demo/town-square",
        },
    )

    assert response.status_code == 200
    assert response.json() == {
        "success": True,
        "alias": "town",
        "channel_id": "town-channel-id",
        "message": "Channel alias town added.",
    }
    assert ctx.user_channels.get_by_owner_and_alias("alice-id", "town").channel_id == (
        "town-channel-id"
    )


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
        "attachments",
    }
    assert payload["drafts"][0]["id"] == draft.id
    assert payload["drafts"][0]["message"] == "Hello from API"
    assert payload["drafts"][0]["status"] == "draft"
    assert payload["csrf"]


def test_api_create_draft_returns_id(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post("/api/web/drafts", data={"csrf": csrf, "message": "  New API draft  "})

    assert response.status_code == 200
    draft_id = response.json()["id"]
    assert ctx.post_drafts.get_for_owner("alice-id", draft_id).message == "New API draft"


def test_api_create_draft_returns_localized_error(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_preferences.set_locale("alice-id", "ru")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post("/api/web/drafts", data={"csrf": csrf, "message": "   "})

    assert response.status_code == 400
    assert response.json() == {"detail": "Текст черновика не может быть пустым"}


def test_api_update_draft_returns_id(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Old",
        message_sha256="old-hash",
    )
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        f"/api/web/drafts/{draft.id}",
        data={"csrf": csrf, "message": "Updated"},
    )

    assert response.status_code == 200
    assert response.json() == {"id": draft.id}
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).message == "Updated"


def test_api_draft_detail_returns_draft(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
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
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Detail draft",
        message_sha256="hash",
    )

    response = client.get(f"/api/web/drafts/{draft.id}")

    assert response.status_code == 200
    payload = response.json()
    assert payload["draft"]["id"] == draft.id
    assert payload["draft"]["message"] == "Detail draft"
    assert payload["draft"]["attachments"] == []
    assert payload["bots"][0]["alias"] == "news"
    assert payload["channels"][0]["alias"] == "town"
    assert payload["default"] == {"bot_alias": "news", "channel_alias": "town"}
    assert payload["stale_default"] is False
    assert payload["target_health"]["status"] == "ok"


def test_api_draft_detail_reports_default_bot_missing_from_channel(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
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
    ctx.token_channel_members[("secret-token", "channel-id", "bot-id")] = MattermostError(
        403,
        "You do not have the appropriate permissions.",
    )
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Detail draft",
        message_sha256="hash",
    )

    response = client.get(f"/api/web/drafts/{draft.id}")

    assert response.status_code == 200
    assert response.json()["target_health"] == {
        "status": "bot_not_in_channel",
        "bot_alias": "news",
        "bot_username": "news-bot",
        "channel_alias": "town",
        "channel_id": "channel-id",
    }


def test_api_upload_image_attachment_returns_preview_and_draft_payload(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Draft with image",
        message_sha256="hash",
    )
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        f"/api/web/drafts/{draft.id}/attachments",
        data={"csrf": csrf},
        files={"file": ("launch.png", b"pngdata", "image/png")},
    )

    assert response.status_code == 200
    attachment = response.json()["attachment"]
    assert attachment["filename"] == "launch.png"
    assert attachment["content_type"] == "image/png"
    assert attachment["size_bytes"] == 7
    assert attachment["preview_url"] == (
        f"/api/web/drafts/{draft.id}/attachments/{attachment['id']}/content"
    )
    preview = client.get(attachment["preview_url"])
    assert preview.status_code == 200
    assert preview.content == b"pngdata"
    assert preview.headers["content-type"] == "image/png"

    detail = client.get(f"/api/web/drafts/{draft.id}")
    assert detail.status_code == 200
    assert detail.json()["draft"]["attachments"] == [attachment]


def test_api_upload_attachment_rejects_non_image(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Draft with invalid file",
        message_sha256="hash",
    )
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        f"/api/web/drafts/{draft.id}/attachments",
        data={"csrf": csrf},
        files={"file": ("notes.txt", b"hello", "text/plain")},
    )

    assert response.status_code == 400
    assert ctx.draft_attachments.list_for_draft("alice-id", draft.id) == []


def test_api_publish_draft_returns_audit_redirect_target(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
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
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Publish from API",
        message_sha256="hash",
    )
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(f"/api/web/drafts/{draft.id}/publish", data={"csrf": csrf})

    assert response.status_code == 200
    assert response.json()["redirect"] == f"/audit?published={draft.id}"
    assert ctx.created_posts[0]["message"] == "Publish from API"
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "sent"


def test_api_publish_draft_returns_localized_error(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_preferences.set_locale("alice-id", "ru")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Publish without default",
        message_sha256="hash",
    )
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(f"/api/web/drafts/{draft.id}/publish", data={"csrf": csrf})

    assert response.status_code == 400
    assert response.json() == {"detail": "Bot/channel по умолчанию не настроены."}


def test_api_delete_draft_soft_deletes(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Delete me",
        message_sha256="hash",
    )
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(f"/api/web/drafts/{draft.id}/delete", data={"csrf": csrf})

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "deleted"


def test_api_delete_draft_returns_404_for_missing_draft(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post("/api/web/drafts/999/delete", data={"csrf": csrf})

    assert response.status_code == 404


def test_api_targets_default_set_and_clear(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
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
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/default",
        data={"csrf": csrf, "bot_alias": "news", "channel_alias": "town"},
    )

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert ctx.user_post_defaults.get_for_owner("alice-id").bot.alias == "news"

    response = client.post("/api/web/targets/default/clear", data={"csrf": csrf})

    assert response.status_code == 200
    assert response.json() == {"success": True}
    assert ctx.user_post_defaults.get_for_owner("alice-id") is None


def test_api_targets_default_rejects_bot_that_is_not_in_channel(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_preferences.set_locale("alice-id", "ru")
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
    ctx.token_channel_members[("secret-token", "channel-id", "bot-id")] = MattermostError(
        403,
        "You do not have the appropriate permissions.",
    )
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/default",
        data={"csrf": csrf, "bot_alias": "news", "channel_alias": "town"},
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Сначала добавьте бота news-bot в Mattermost-канал town."
    }
    assert ctx.user_post_defaults.get_for_owner("alice-id") is None


def test_api_targets_default_rejects_invalid_aliases_with_localized_error(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_preferences.set_locale("alice-id", "ru")
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post(
        "/api/web/targets/default",
        data={"csrf": csrf, "bot_alias": "missing", "channel_alias": "missing"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Target aliases указаны неверно"}


def test_api_language_changes_locale(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = client.get("/api/web/bootstrap").json()["csrf"]

    response = client.post("/api/web/language", data={"csrf": csrf, "locale": "ru"})

    assert response.status_code == 200
    assert response.json() == {"locale": "ru"}
    assert ctx.user_preferences.get_locale("alice-id") == "ru"


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
