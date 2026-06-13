# ruff: noqa: RUF001
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from importlib.util import find_spec
from typing import Any, cast

import pytest
from testcontainers.postgres import PostgresContainer

from mm_post_bot.commands import CommandContext, dispatch
from mm_post_bot.config import Settings
from mm_post_bot.db import DbConn, connect_postgres, init_schema
from mm_post_bot.dispatcher import CommandContextFactory
from mm_post_bot.mm_client import MattermostClient, MattermostError
from mm_post_bot.repository import (
    AuditRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPostDefault,
    UserPostDefaultRepo,
    UserPreferenceRepo,
    UserRepo,
)
from mm_post_bot.security import encrypt_token, fingerprint_token, hash_message

POSTGRES_IMAGE = "postgres:15-alpine"


class FakeMM:
    def __init__(self) -> None:
        self.users_by_username: dict[str, dict[str, Any] | BaseException] = {}
        self.direct_channels: list[tuple[str, str]] = []
        self.posts: list[dict[str, str]] = []

    async def get_user_by_username(self, username: str) -> dict[str, Any]:
        try:
            user = self.users_by_username[username]
        except KeyError as exc:
            raise AssertionError(f"unexpected admin lookup for {username}") from exc
        if isinstance(user, BaseException):
            raise user
        return user

    async def create_direct_channel(self, user_id_a: str, user_id_b: str) -> dict[str, Any]:
        self.direct_channels.append((user_id_a, user_id_b))
        return {"id": f"dm-{user_id_a}-{user_id_b}"}

    async def create_post(self, channel_id: str, message: str) -> dict[str, Any]:
        self.posts.append({"channel_id": channel_id, "message": message})
        return {"id": "post-id", "channel_id": channel_id, "message": message}


class FakeTokenMM:
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

    async def get_me(self) -> dict[str, Any]:
        try:
            identity = TOKEN_IDENTITIES[self.token]
        except KeyError as exc:
            raise AssertionError(f"unexpected token validation for {self.token}") from exc
        if isinstance(identity, BaseException):
            raise identity
        return identity

    async def get_channel_by_team_and_name(
        self,
        team_name: str,
        channel_name: str,
    ) -> dict[str, Any]:
        try:
            channel = TOKEN_CHANNELS[(self.token, team_name, channel_name)]
        except KeyError as exc:
            raise AssertionError(
                f"unexpected channel lookup for {self.token}/{team_name}/{channel_name}"
            ) from exc
        if isinstance(channel, BaseException):
            raise channel
        return channel

    async def create_post(self, channel_id: str, message: str) -> dict[str, Any]:
        configured = TOKEN_POST_RESULTS.get((self.token, channel_id))
        if isinstance(configured, BaseException):
            raise configured
        if configured is not None:
            post = configured | {"channel_id": channel_id, "message": message, "token": self.token}
            CREATED_POSTS.append(post)
            return post

        post = {
            "id": f"post-{len(CREATED_POSTS) + 1}",
            "channel_id": channel_id,
            "message": message,
            "token": self.token,
        }
        CREATED_POSTS.append(post)
        return post

    async def aclose(self) -> None:
        pass


class BrokenAuditRepo:
    def record(self, **kwargs: Any) -> None:
        raise RuntimeError("audit unavailable")


TOKEN_IDENTITIES: dict[str, dict[str, Any] | BaseException] = {}
TOKEN_CHANNELS: dict[tuple[str, str, str], dict[str, Any] | BaseException] = {}
TOKEN_POST_RESULTS: dict[tuple[str, str], dict[str, Any] | BaseException] = {}
CREATED_POSTS: list[dict[str, Any]] = []
FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


@dataclass(frozen=True, slots=True)
class CommandFixture:
    conn: DbConn
    users: UserRepo
    user_preferences: UserPreferenceRepo
    user_bots: UserBotRepo
    user_channels: UserChannelRepo
    user_post_defaults: UserPostDefaultRepo
    draft_captures: DraftCaptureRepo
    post_drafts: PostDraftRepo
    audits: AuditRepo
    manager_mm: FakeMM
    token_identities: dict[str, dict[str, Any] | BaseException]
    token_channels: dict[tuple[str, str, str], dict[str, Any] | BaseException]
    token_post_results: dict[tuple[str, str], dict[str, Any] | BaseException]
    created_posts: list[dict[str, Any]]

    def make(
        self,
        caller_user_id: str,
        caller_username: str,
        *,
        admin_usernames: set[str] | frozenset[str] | None = None,
        channel_type: str | None = "D",
    ) -> CommandContext:
        return CommandContext(
            caller_user_id=caller_user_id,
            caller_username=caller_username,
            channel_id="dm-channel",
            channel_type=channel_type,
            user_repo=self.users,
            user_preference_repo=self.user_preferences,
            user_bot_repo=self.user_bots,
            user_channel_repo=self.user_channels,
            user_post_default_repo=self.user_post_defaults,
            draft_capture_repo=self.draft_captures,
            post_draft_repo=self.post_drafts,
            audit_repo=self.audits,
            manager_mm=cast(MattermostClient, self.manager_mm),
            manager_user_id="manager-id",
            admin_usernames=frozenset(admin_usernames or set()),
            mm_rest_base="https://mm.internal/api/v4",
            mm_url="https://mm.internal",
            token_encryption_key=FERNET_KEY,
            mm_verify_ssl=True,
            default_locale="en",
            locale=self.user_preferences.get_locale(caller_user_id) or "en",
        )


@pytest.fixture(scope="session")
def pg_conn() -> DbConn:
    with PostgresContainer(POSTGRES_IMAGE) as pg:
        url = pg.get_connection_url()
        dsn = url.split("+")[0] + "://" + url.split("://")[1]
        conn = connect_postgres(dsn)
        init_schema(conn)
        yield conn
        conn.close()


@pytest.fixture()
def ctx(pg_conn: DbConn, monkeypatch: pytest.MonkeyPatch) -> CommandFixture:
    pg_conn.execute("BEGIN")
    TOKEN_IDENTITIES.clear()
    TOKEN_CHANNELS.clear()
    TOKEN_POST_RESULTS.clear()
    CREATED_POSTS.clear()
    if find_spec("mm_post_bot.commands.bot") is not None:
        monkeypatch.setattr("mm_post_bot.commands.bot.MattermostClient", FakeTokenMM)
    if find_spec("mm_post_bot.commands.send") is not None:
        monkeypatch.setattr("mm_post_bot.commands.send.MattermostClient", FakeTokenMM)

    users = UserRepo(pg_conn)
    yield CommandFixture(
        conn=pg_conn,
        users=users,
        user_preferences=UserPreferenceRepo(pg_conn),
        user_bots=UserBotRepo(pg_conn),
        user_channels=UserChannelRepo(pg_conn),
        user_post_defaults=UserPostDefaultRepo(pg_conn),
        draft_captures=DraftCaptureRepo(pg_conn),
        post_drafts=PostDraftRepo(pg_conn),
        audits=AuditRepo(pg_conn),
        manager_mm=FakeMM(),
        token_identities=TOKEN_IDENTITIES,
        token_channels=TOKEN_CHANNELS,
        token_post_results=TOKEN_POST_RESULTS,
        created_posts=CREATED_POSTS,
    )
    TOKEN_IDENTITIES.clear()
    TOKEN_CHANNELS.clear()
    TOKEN_POST_RESULTS.clear()
    CREATED_POSTS.clear()
    pg_conn.execute("ROLLBACK")


def test_context_factory_uses_default_locale_without_preference(pg_conn: DbConn):
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="levonti",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=FERNET_KEY,
        default_locale="ru",
    )
    factory = CommandContextFactory(
        conn=pg_conn,
        settings=settings,
        manager_mm=cast(MattermostClient, FakeMM()),
        manager_user_id="mgr",
    )

    ctx = factory.from_post({"user_id": "u-locale-default", "sender_name": "alice"}, "D")

    assert ctx.locale == "ru"
    assert ctx.default_locale == "ru"


def test_context_factory_uses_stored_user_locale(pg_conn: DbConn):
    pg_conn.execute("BEGIN")
    try:
        UserPreferenceRepo(pg_conn).set_locale("u-locale-stored", "ru")
        settings = Settings(
            mm_url="https://mm.internal",
            mm_bot_token="manager-token",
            mm_admins="levonti",
            db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
            token_encryption_key=FERNET_KEY,
            default_locale="en",
        )
        factory = CommandContextFactory(
            conn=pg_conn,
            settings=settings,
            manager_mm=cast(MattermostClient, FakeMM()),
            manager_user_id="mgr",
        )

        ctx = factory.from_post({"user_id": "u-locale-stored", "sender_name": "alice"}, "D")

        assert ctx.locale == "ru"
        assert ctx.t("lang.changed.ru") == "Язык изменён на русский."
    finally:
        pg_conn.execute("ROLLBACK")


async def test_register_creates_pending_user(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!register")
    assert reply is not None
    assert "pending" in reply.lower()
    assert ctx.users.get("alice-id").status == "pending"


async def test_register_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!register")

    assert reply is not None
    assert "Пользователь alice зарегистрирован как user" in reply
    assert "Текущий статус: pending" in reply


async def test_register_notifies_configured_admins(ctx: CommandFixture):
    ctx.manager_mm.users_by_username["admin"] = {"id": "admin-id", "username": "admin"}

    reply = await dispatch(
        ctx.make("alice-id", "@alice", admin_usernames={"admin"}),
        "!register",
    )

    assert reply is not None
    assert "pending" in reply.lower()
    assert ctx.manager_mm.direct_channels == [("manager-id", "admin-id")]
    assert ctx.manager_mm.posts == [
        {
            "channel_id": "dm-manager-id-admin-id",
            "message": (
                "New registration request from alice (alice-id).\nApprove with: !user approve alice"
            ),
        }
    ]


async def test_registration_request_notification_uses_admin_locale(ctx: CommandFixture):
    ctx.manager_mm.users_by_username["admin"] = {"id": "admin-id", "username": "admin"}
    await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!lang ru")

    await dispatch(ctx.make("alice-id", "alice", admin_usernames={"admin"}), "!register")

    assert ctx.manager_mm.posts == [
        {
            "channel_id": "dm-manager-id-admin-id",
            "message": (
                "Новая заявка на регистрацию от alice (alice-id).\nПодтвердить: !user approve alice"
            ),
        }
    ]


async def test_register_notification_failures_do_not_block_registration(ctx: CommandFixture):
    ctx.manager_mm.users_by_username["admin"] = MattermostError(404, "missing")

    reply = await dispatch(
        ctx.make("alice-id", "alice", admin_usernames={"admin"}),
        "!register",
    )

    assert reply is not None
    assert "pending" in reply.lower()
    assert ctx.users.get("alice-id").status == "pending"
    assert ctx.manager_mm.posts == []


async def test_admin_registers_as_approved_with_bootstrap_message(ctx: CommandFixture):
    reply = await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!register")

    assert reply is not None
    assert "Registered admin as admin" in reply
    assert "approved automatically" in reply
    assert "MM_ADMINS" in reply
    assert ctx.users.get("admin-id").role == "admin"
    assert ctx.users.get("admin-id").status == "approved"
    assert ctx.manager_mm.posts == []


async def test_admin_registers_as_approved_with_mention_style_username(ctx: CommandFixture):
    reply = await dispatch(ctx.make("admin-id", "@admin", admin_usernames={"admin"}), "!register")

    assert reply is not None
    assert "Registered admin as admin" in reply
    assert "approved automatically" in reply
    assert ctx.users.get("admin-id").username == "admin"
    assert ctx.users.get("admin-id").role == "admin"


async def test_user_approve_requires_admin(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    reply = await dispatch(ctx.make("bob-id", "bob"), "!user approve alice")
    assert reply is not None
    assert "admin" in reply.lower()


async def test_configured_admin_can_approve_without_local_registration(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")

    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!user approve alice",
    )

    assert reply is not None
    assert "Approved alice" in reply
    assert ctx.users.get("alice-id").status == "approved"
    with pytest.raises(LookupError):
        ctx.users.get("admin-id")


async def test_admin_can_approve_block_and_unblock(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    admin_ctx = ctx.make("admin-id", "admin", admin_usernames={"admin"})

    approve = await dispatch(admin_ctx, "!user approve alice")
    assert approve is not None
    assert "approved" in approve.lower()
    assert ctx.users.get("alice-id").status == "approved"
    assert ctx.manager_mm.posts[-1] == {
        "channel_id": "dm-manager-id-alice-id",
        "message": "Your mm-post-bot access has been approved.",
    }

    block = await dispatch(admin_ctx, "!user block alice")
    assert block is not None
    assert "blocked" in block.lower()
    assert ctx.users.get("alice-id").status == "blocked"
    assert ctx.manager_mm.posts[-1] == {
        "channel_id": "dm-manager-id-alice-id",
        "message": "Your mm-post-bot access has been blocked.",
    }

    unblock = await dispatch(admin_ctx, "!user unblock alice")
    assert unblock is not None
    assert "approved" in unblock.lower()
    assert ctx.users.get("alice-id").status == "approved"
    assert ctx.manager_mm.posts[-1] == {
        "channel_id": "dm-manager-id-alice-id",
        "message": "Your mm-post-bot access has been unblocked and approved.",
    }


async def test_admin_can_approve_mention_style_target(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "@alice"), "!register")
    admin_ctx = ctx.make("admin-id", "@admin", admin_usernames={"admin"})
    await dispatch(admin_ctx, "!register")

    approve = await dispatch(admin_ctx, "!user approve @alice")

    assert approve is not None
    assert "approved" in approve.lower()
    assert ctx.users.get("alice-id").status == "approved"


async def test_user_status_notification_failure_does_not_block_admin_action(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")

    async def broken_create_post(channel_id: str, message: str) -> dict[str, Any]:
        raise MattermostError(500, "post failed")

    ctx.manager_mm.create_post = broken_create_post  # type: ignore[method-assign]

    approve = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!user approve alice",
    )

    assert approve is not None
    assert "approved" in approve.lower()
    assert ctx.users.get("alice-id").status == "approved"


async def test_configured_admins_cannot_be_blocked(ctx: CommandFixture):
    root_ctx = ctx.make("root-id", "root", admin_usernames={"admin", "root"})
    await dispatch(root_ctx, "!register")

    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin", "root"}),
        "!user block root",
    )

    assert reply is not None
    assert "cannot be blocked" in reply.lower()
    assert ctx.users.get("root-id").status == "approved"


async def test_status_reports_unknown_pending_approved_and_blocked(ctx: CommandFixture):
    unknown = await dispatch(ctx.make("alice-id", "alice"), "!status")
    assert unknown is not None
    assert "!register" in unknown

    await dispatch(ctx.make("alice-id", "alice"), "!register")
    pending = await dispatch(ctx.make("alice-id", "alice"), "!status")
    assert pending is not None
    assert "pending" in pending.lower()

    await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!register")
    await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!user approve alice")
    approved = await dispatch(ctx.make("alice-id", "alice"), "!status")
    assert approved is not None
    assert "approved" in approved.lower()

    await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!user block alice")
    blocked = await dispatch(ctx.make("alice-id", "alice"), "!status")
    assert blocked is not None
    assert "blocked" in blocked.lower()


async def test_status_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!status")

    assert reply == "alice: статус pending, роль user."


async def test_admin_lists_pending_users(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    await dispatch(ctx.make("bob-id", "bob"), "!register")

    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!user list pending",
    )

    assert reply is not None
    assert "alice" in reply
    assert "bob" in reply
    assert "pending" in reply


async def test_user_list_requires_admin(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!user list pending")
    assert reply is not None
    assert "admin" in reply.lower()


async def test_non_bang_help_returns_prefix_message(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "help")
    assert reply == "All commands must start with !."


async def test_lang_shows_current_language_before_registration(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!lang")

    assert reply == "Current language: en. Supported languages: en, ru."


async def test_lang_changes_language_before_registration(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    assert reply == "Язык изменён на русский."
    assert ctx.user_preferences.get_locale("alice-id") == "ru"


async def test_lang_rejects_unknown_locale(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!lang fr")

    assert reply == "Unsupported language: fr. Supported languages: en, ru."


async def test_lang_command_name_stays_english_only(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!язык ru")

    assert reply == "Unknown command: язык"
    assert ctx.user_preferences.get_locale("alice-id") is None


async def test_dispatcher_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    missing_bang = await dispatch(ctx.make("alice-id", "alice"), "help")
    unknown = await dispatch(ctx.make("alice-id", "alice"), "!unknown")

    assert missing_bang == "Все команды должны начинаться с !."
    assert unknown == "Неизвестная команда: unknown"


async def test_access_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot list")

    assert reply == "Вы ещё не зарегистрированы. Выполните !register, чтобы запросить доступ."


async def test_help_shows_admin_bootstrap_for_unregistered_configured_admin(
    ctx: CommandFixture,
):
    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!help",
    )

    assert reply is not None
    assert "Admin bootstrap" in reply
    assert "configured as an admin" in reply
    assert "Run !register" in reply
    assert "!user approve <username|user_id>" in reply
    assert "!bot add" not in reply
    assert "!send" not in reply


async def test_help_shows_admin_bootstrap_for_mention_style_configured_admin(
    ctx: CommandFixture,
):
    reply = await dispatch(
        ctx.make("admin-id", "@admin", admin_usernames={"admin"}),
        "!help",
    )

    assert reply is not None
    assert "Admin bootstrap" in reply
    assert "!user approve <username|user_id>" in reply


async def test_help_changes_after_user_approval(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")

    pending = await dispatch(ctx.make("alice-id", "alice"), "!help")
    assert pending is not None
    assert "!register" in pending
    assert "!bot add" not in pending
    assert "!send" not in pending

    await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!register")
    await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!user approve alice")

    approved = await dispatch(ctx.make("alice-id", "alice"), "!help")
    assert approved is not None
    assert "!bot add <alias> <token>" in approved
    assert "!channel add <alias> <channel_id>" in approved
    assert "!channel set <alias> <channel_id>" in approved
    assert "!draft" in approved
    assert "!send <draft_id> [--bot <alias>] [--channel <channel_alias>]" in approved


async def test_help_includes_default_commands_for_approved_user(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!help")

    assert reply is not None
    assert "!default" in reply
    assert "!default set --bot <alias> --channel <channel_alias>" in reply
    assert "!default clear" in reply


async def test_help_keeps_posting_commands_from_blocked_user(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.block("alice-id", blocked_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!help")

    assert reply is not None
    assert "!status" in reply
    assert "!bot add" not in reply
    assert "!send" not in reply


async def test_help_shows_admin_commands_for_mention_style_admin(ctx: CommandFixture):
    await dispatch(ctx.make("admin-id", "@admin", admin_usernames={"admin"}), "!register")

    reply = await dispatch(ctx.make("admin-id", "@admin", admin_usernames={"admin"}), "!help")

    assert reply is not None
    assert "!bot add" in reply
    assert "!user approve" in reply


async def test_help_mentions_lang_command(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!help")

    assert reply is not None
    assert "!lang [en|ru]" in reply


async def test_help_uses_selected_locale_but_keeps_commands_english(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!help")

    assert reply is not None
    assert "Основное:" in reply
    assert "!register - запросить доступ к постингу" in reply
    assert "!lang [en|ru]" in reply


async def test_user_status_notification_uses_target_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice", admin_usernames={"admin"}), "!register")

    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!user approve alice",
    )

    assert reply is not None
    assert "Approved alice" in reply
    assert ctx.manager_mm.posts[-1] == {
        "channel_id": "dm-manager-id-alice-id",
        "message": "Ваш доступ к mm-post-bot подтверждён.",
    }


async def test_bot_add_requires_approved_user(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add news token")
    assert reply is not None
    assert "approval" in reply.lower()


async def test_bot_add_requires_dm(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    reply = await dispatch(ctx.make("alice-id", "alice", channel_type="O"), "!bot add news token")
    assert reply is not None
    assert "direct message" in reply.lower()


async def test_bot_add_validates_and_encrypts_token(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    assert reply is not None
    assert "added" in reply.lower()
    saved = ctx.user_bots.get_by_owner_and_alias("alice-id", "news")
    assert saved.bot_user_id == "bot-id"
    assert saved.token_ciphertext != "secret-token"


async def test_bot_list_and_remove(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")

    listed = await dispatch(ctx.make("alice-id", "alice"), "!bot list")
    assert listed is not None
    assert "news" in listed
    assert "secret-token" not in listed

    removed = await dispatch(ctx.make("alice-id", "alice"), "!bot remove news")
    assert removed is not None
    assert "removed" in removed.lower()


@pytest.mark.parametrize("command", ["!bot add news token", "!bot list", "!bot remove news"])
async def test_bot_commands_reject_blocked_user(ctx: CommandFixture, command: str):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.block("alice-id", blocked_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), command)

    assert reply is not None
    assert "blocked" in reply.lower()


async def test_draft_start_requires_approved_user(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!draft")

    assert reply is not None
    assert "approval" in reply.lower()
    assert ctx.draft_captures.get_active("alice-id", now=datetime.now(UTC)) is None


async def test_draft_start_requires_dm(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice", channel_type="O"), "!draft")

    assert reply is not None
    assert "direct message" in reply.lower()
    assert ctx.draft_captures.get_active("alice-id", now=datetime.now(UTC)) is None


async def test_draft_start_creates_capture(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!draft")

    assert reply is not None
    assert "send the post body" in reply.lower()
    capture = ctx.draft_captures.get_active("alice-id", now=datetime.now(UTC))
    assert capture is not None
    assert capture.expires_at > datetime.now(UTC)


async def test_draft_cancel_clears_capture(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    await dispatch(ctx.make("alice-id", "alice"), "!draft")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!draft cancel")

    assert reply is not None
    assert "cancelled" in reply.lower()
    assert ctx.draft_captures.get_active("alice-id", now=datetime.now(UTC)) is None


async def test_draft_list_show_and_delete_only_use_own_draft_status(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.upsert_seen_user(user_id="bob-id", username="bob", is_admin=False)
    ctx.users.approve("bob-id", approved_by="admin-id")
    own = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="own visible body",
        message_sha256="own-hash",
    )
    other = ctx.post_drafts.create(
        owner_user_id="bob-id",
        message="other secret body",
        message_sha256="other-hash",
    )
    deleted = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="deleted secret body",
        message_sha256="deleted-hash",
    )
    sent = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="sent secret body",
        message_sha256="sent-hash",
    )
    ctx.post_drafts.soft_delete("alice-id", deleted.id)
    ctx.conn.execute("UPDATE post_draft SET status = 'sent' WHERE id = %s", (sent.id,))

    listed = await dispatch(ctx.make("alice-id", "alice"), "!draft list")
    assert listed is not None
    assert f"#{own.id}" in listed
    assert f"#{deleted.id}" not in listed
    assert f"#{sent.id}" not in listed
    assert "secret body" not in listed

    shown = await dispatch(ctx.make("alice-id", "alice"), f"!draft show {own.id}")
    assert shown is not None
    assert "own visible body" in shown

    for hidden in (other, deleted, sent):
        hidden_reply = await dispatch(ctx.make("alice-id", "alice"), f"!draft show {hidden.id}")
        assert hidden_reply is not None
        assert "not found" in hidden_reply.lower()
        assert "secret body" not in hidden_reply

    deleted_reply = await dispatch(ctx.make("alice-id", "alice"), f"!draft delete {own.id}")
    assert deleted_reply is not None
    assert "deleted" in deleted_reply.lower()
    assert ctx.post_drafts.get_for_owner("alice-id", own.id).status == "deleted"


async def test_draft_show_includes_ready_target_context(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    await dispatch(ctx.make("alice-id", "alice"), "!default set --bot news --channel town")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Release notes\nSecond line",
        message_sha256=hash_message("Release notes\nSecond line"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!draft show {draft.id}")

    assert reply is not None
    assert f"Draft #{draft.id}" in reply
    assert "Release notes\nSecond line" in reply
    assert "Target: bot news (news-bot), channel town (channel-id)" in reply
    assert f"Publish: !send {draft.id}" in reply
    assert f"Delete: !draft delete {draft.id}" in reply


async def test_draft_show_includes_missing_target_recovery(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Body without defaults",
        message_sha256=hash_message("Body without defaults"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!draft show {draft.id}")

    assert reply is not None
    assert "Target: no default bot/channel configured" in reply
    assert "!default set --bot <alias> --channel <channel_alias>" in reply
    assert f"!send {draft.id} --bot <alias> --channel <channel_alias>" in reply


@pytest.mark.parametrize(
    "command",
    ["!draft", "!draft cancel", "!draft list", "!draft show 1", "!draft delete 1"],
)
async def test_draft_commands_reject_blocked_user(ctx: CommandFixture, command: str):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.block("alice-id", blocked_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), command)

    assert reply is not None
    assert "blocked" in reply.lower()


async def test_draft_flow_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")

    started = await dispatch(ctx.make("alice-id", "alice"), "!draft")
    cancelled = await dispatch(ctx.make("alice-id", "alice"), "!draft cancel")

    assert started == "Ожидание черновика включено. Отправьте текст поста в этом direct message."
    assert cancelled == "Ожидание черновика отменено."


async def test_bot_add_rejects_non_bot_token(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["human-token"] = {
        "id": "human-id",
        "username": "alice",
        "is_bot": False,
    }

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add personal human-token")

    assert reply is not None
    assert "bot token" in reply.lower()
    with pytest.raises(LookupError):
        ctx.user_bots.get_by_owner_and_alias("alice-id", "personal")


async def test_bot_validation_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["human-token"] = {
        "id": "human-id",
        "username": "alice",
        "is_bot": False,
    }

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add personal human-token")

    assert reply == "Этот token принадлежит обычному пользователю. Укажите token бота."


async def test_bot_add_rejects_missing_bot_flag(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["ambiguous-token"] = {
        "id": "human-id",
        "username": "alice",
    }

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add personal ambiguous-token")

    assert reply is not None
    assert "bot token" in reply.lower()
    with pytest.raises(LookupError):
        ctx.user_bots.get_by_owner_and_alias("alice-id", "personal")


async def test_bot_add_handles_invalid_token(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["bad-token"] = MattermostError(401, "invalid token")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add news bad-token")

    assert reply is not None
    assert "could not validate" in reply.lower()
    assert "bad-token" not in reply
    with pytest.raises(LookupError):
        ctx.user_bots.get_by_owner_and_alias("alice-id", "news")


async def test_bot_add_response_does_not_include_token(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["super-secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add news super-secret-token")

    assert reply is not None
    assert "super-secret-token" not in reply


async def test_channel_add_lists_shows_sets_and_removes_alias(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    added = await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")

    assert added is not None
    assert "added" in added.lower()
    assert ctx.user_channels.get_by_owner_and_alias("alice-id", "town").channel_id == "channel-id"

    listed = await dispatch(ctx.make("alice-id", "alice"), "!channel list")
    assert listed is not None
    assert "town - channel-id" in listed

    shown = await dispatch(ctx.make("alice-id", "alice"), "!channel show town")
    assert shown is not None
    assert "town - channel-id" in shown

    updated = await dispatch(ctx.make("alice-id", "alice"), "!channel set town new-channel-id")
    assert updated is not None
    assert "updated" in updated.lower()
    assert (
        ctx.user_channels.get_by_owner_and_alias("alice-id", "town").channel_id == "new-channel-id"
    )

    removed = await dispatch(ctx.make("alice-id", "alice"), "!channel remove town")
    assert removed is not None
    assert "removed" in removed.lower()
    with pytest.raises(LookupError):
        ctx.user_channels.get_by_owner_and_alias("alice-id", "town")


async def test_channel_add_current_saves_current_channel_id(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    channel_ctx = ctx.make("alice-id", "alice", channel_type="O")
    channel_ctx = replace(channel_ctx, channel_id="current-channel-id")

    reply = await dispatch(channel_ctx, "!channel add-current town")

    assert reply is not None
    assert "added" in reply.lower()
    saved = ctx.user_channels.get_by_owner_and_alias("alice-id", "town")
    assert saved.channel_id == "current-channel-id"


async def test_channel_add_current_rejects_dm_duplicate_and_unapproved_user(
    ctx: CommandFixture,
):
    pending = await dispatch(
        ctx.make("alice-id", "alice", channel_type="O"),
        "!channel add-current town",
    )
    assert pending is not None
    assert "register" in pending.lower()

    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    dm_reply = await dispatch(ctx.make("alice-id", "alice"), "!channel add-current town")
    assert dm_reply is not None
    assert "channel" in dm_reply.lower()

    channel_ctx = replace(
        ctx.make("alice-id", "alice", channel_type="O"),
        channel_id="current-channel-id",
    )
    await dispatch(channel_ctx, "!channel add-current town")
    duplicate = await dispatch(channel_ctx, "!channel add-current town")
    assert duplicate is not None
    assert "already" in duplicate.lower()


async def test_channel_aliases_are_owner_scoped(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.upsert_seen_user(user_id="bob-id", username="bob", is_admin=False)
    ctx.users.approve("bob-id", approved_by="admin-id")

    await dispatch(ctx.make("alice-id", "alice"), "!channel add town alice-channel")
    await dispatch(ctx.make("bob-id", "bob"), "!channel add town bob-channel")

    alice_channel = ctx.user_channels.get_by_owner_and_alias("alice-id", "town")
    assert alice_channel.channel_id == "alice-channel"
    assert ctx.user_channels.get_by_owner_and_alias("bob-id", "town").channel_id == "bob-channel"


async def test_channel_add_rejects_duplicate_alias_and_links(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")

    duplicate = await dispatch(ctx.make("alice-id", "alice"), "!channel add town other-channel")
    link = await dispatch(
        ctx.make("alice-id", "alice"),
        "!channel add link https://mm.internal/team/channels/town-square",
    )

    assert duplicate is not None
    assert "already" in duplicate.lower()
    assert link is not None
    assert "channel id" in link.lower()
    assert "link" in link.lower()


async def test_channel_errors_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        "!channel add town https://mm.internal/team/channels/town",
    )

    assert reply == "Укажите Mattermost channel id, а не ссылку на канал."


@pytest.mark.parametrize(
    "command",
    [
        "!channel add town channel-id",
        "!channel set town channel-id",
        "!channel remove town",
        "!channel list",
        "!channel show town",
    ],
)
async def test_channel_commands_reject_blocked_user(ctx: CommandFixture, command: str):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.block("alice-id", blocked_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), command)

    assert reply is not None
    assert "blocked" in reply.lower()


@pytest.mark.parametrize(
    "command",
    [
        "!channel add town channel-id",
        "!channel set town channel-id",
        "!channel remove town",
        "!channel list",
        "!channel show town",
    ],
)
async def test_channel_commands_require_dm(ctx: CommandFixture, command: str):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice", channel_type="O"), command)

    assert reply is not None
    assert "direct message" in reply.lower()


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("!channel add town", "usage"),
        ("!channel set town", "usage"),
        ("!channel remove", "usage"),
        ("!channel show", "usage"),
    ],
)
async def test_channel_commands_validate_args(
    ctx: CommandFixture,
    command: str,
    expected: str,
):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), command)

    assert reply is not None
    assert expected in reply.lower()


async def test_default_shows_empty_state(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!default")

    assert reply is not None
    assert "no default" in reply.lower()


async def test_default_set_show_and_clear(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")

    set_reply = await dispatch(
        ctx.make("alice-id", "alice"),
        "!default set --bot news --channel town",
    )
    show_reply = await dispatch(ctx.make("alice-id", "alice"), "!default")
    clear_reply = await dispatch(ctx.make("alice-id", "alice"), "!default clear")
    empty_reply = await dispatch(ctx.make("alice-id", "alice"), "!default")

    assert set_reply is not None
    assert "news" in set_reply
    assert "town" in set_reply
    assert show_reply is not None
    assert "news" in show_reply
    assert "town" in show_reply
    assert "channel-id" in show_reply
    assert clear_reply is not None
    assert "cleared" in clear_reply.lower()
    assert empty_reply is not None
    assert "no default" in empty_reply.lower()


async def test_default_shows_stale_state(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    await dispatch(ctx.make("alice-id", "alice"), "!default set --bot news --channel town")
    ctx.user_bots.soft_delete("alice-id", "news")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!default")

    assert reply is not None
    assert "removed" in reply.lower()
    assert "!default set --bot <alias> --channel <channel_alias>" in reply


async def test_default_set_rejects_unknown_bot_or_channel(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")

    missing_bot = await dispatch(
        ctx.make("alice-id", "alice"),
        "!default set --bot news --channel town",
    )

    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    missing_channel = await dispatch(
        ctx.make("alice-id", "alice"),
        "!default set --bot news --channel missing",
    )

    assert missing_bot is not None
    assert "bot" in missing_bot.lower()
    assert missing_channel is not None
    assert "channel" in missing_channel.lower()
    assert ctx.user_post_defaults.get_for_owner("alice-id") is None


@pytest.mark.parametrize(
    "command",
    [
        "!default",
        "!default set --bot news --channel town",
        "!default clear",
    ],
)
async def test_default_commands_require_approved_user(ctx: CommandFixture, command: str):
    reply = await dispatch(ctx.make("alice-id", "alice"), command)

    assert reply is not None
    assert "register" in reply.lower()


@pytest.mark.parametrize(
    "command",
    [
        "!default",
        "!default set --bot news --channel town",
        "!default clear",
    ],
)
async def test_default_commands_require_dm(ctx: CommandFixture, command: str):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice", channel_type="O"), command)

    assert reply is not None
    assert "direct message" in reply.lower()


async def test_default_replies_use_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!default")

    assert reply is not None
    assert "по умолчанию" in reply.lower()


async def test_send_posts_saved_draft(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    bot = ctx.user_bots.get_by_owner_and_alias("alice-id", "news")
    message = "Hello from the saved draft"
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message=message,
        message_sha256=hash_message(message),
    )
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel town",
    )

    assert reply is not None
    assert "published" in reply.lower()
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "channel-id",
            "message": message,
            "token": "secret-token",
        }
    ]
    sent = ctx.post_drafts.get_for_owner("alice-id", draft.id)
    assert sent.status == "sent"
    assert sent.sent_by_user_bot_id == bot.id
    assert sent.sent_channel_id == "channel-id"
    assert sent.mattermost_post_id == "post-1"

    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].status == "success"
    assert audits[0].draft_id == draft.id
    assert audits[0].user_bot_id == bot.id
    assert audits[0].bot_user_id == "bot-id"
    assert audits[0].bot_username == "news-bot"
    assert audits[0].channel_link == "town"
    assert audits[0].resolved_channel_id == "channel-id"
    assert audits[0].resolved_team_name is None
    assert audits[0].resolved_channel_name is None
    assert audits[0].message_sha256 == hash_message(message)
    assert audits[0].mattermost_post_id == "post-1"
    assert audits[0].error_code is None
    assert audits[0].error_message is None


async def test_send_uses_configured_defaults(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    await dispatch(ctx.make("alice-id", "alice"), "!default set --bot news --channel town")
    message = "Default target body"
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message=message,
        message_sha256=hash_message(message),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!send {draft.id}")

    assert reply is not None
    assert "published" in reply.lower()
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "channel-id",
            "message": message,
            "token": "secret-token",
        }
    ]
    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].channel_link == "town"
    assert audits[0].resolved_channel_id == "channel-id"


async def test_send_uses_default_rows_when_alias_is_reused(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["old-token"] = {
        "id": "old-bot-id",
        "username": "old-bot",
        "is_bot": True,
    }
    ctx.token_identities["new-token"] = {
        "id": "new-bot-id",
        "username": "new-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news old-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town old-channel")
    await dispatch(ctx.make("alice-id", "alice"), "!default set --bot news --channel town")
    default_before_reuse = ctx.user_post_defaults.get_for_owner("alice-id")
    assert default_before_reuse is not None
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Default row identity",
        message_sha256=hash_message("Default row identity"),
    )
    default_repo = ctx.user_post_defaults

    class AliasReuseDuringDefaultLookup:
        def __init__(self) -> None:
            self.swapped = False

        def get_for_owner(self, owner_user_id: str) -> UserPostDefault | None:
            default = default_repo.get_for_owner(owner_user_id)
            if default is not None and not self.swapped:
                self.swapped = True
                ctx.user_bots.soft_delete(owner_user_id, "news")
                ctx.user_channels.soft_delete(owner_user_id, "town")
                ctx.user_bots.add(
                    owner_user_id=owner_user_id,
                    alias="news",
                    bot_user_id="new-bot-id",
                    bot_username="new-bot",
                    bot_display_name=None,
                    token_ciphertext=encrypt_token("new-token", FERNET_KEY),
                    token_fingerprint=fingerprint_token("new-token"),
                )
                ctx.user_channels.add(
                    owner_user_id=owner_user_id,
                    alias="town",
                    channel_id="new-channel",
                )
            return default

        def has_for_owner(self, owner_user_id: str) -> bool:
            return default_repo.has_for_owner(owner_user_id)

    race_ctx = replace(
        ctx.make("alice-id", "alice"),
        user_post_default_repo=cast(UserPostDefaultRepo, AliasReuseDuringDefaultLookup()),
    )

    reply = await dispatch(race_ctx, f"!send {draft.id}")

    assert reply is not None
    assert "published" in reply.lower()
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "old-channel",
            "message": "Default row identity",
            "token": "old-token",
        }
    ]
    assert (
        ctx.post_drafts.get_for_owner("alice-id", draft.id).sent_by_user_bot_id
        == default_before_reuse.bot.id
    )
    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].bot_username == "old-bot"
    assert audits[0].channel_link == "town"
    assert audits[0].resolved_channel_id == "old-channel"


async def test_send_can_override_default_bot_or_channel(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["news-token"] = {
        "id": "news-bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    ctx.token_identities["alerts-token"] = {
        "id": "alerts-bot-id",
        "username": "alerts-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news news-token")
    await dispatch(ctx.make("alice-id", "alice"), "!bot add alerts alerts-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town town-channel")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add urgent urgent-channel")
    await dispatch(ctx.make("alice-id", "alice"), "!default set --bot news --channel town")
    first = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Override channel",
        message_sha256=hash_message("Override channel"),
    )
    second = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Override bot",
        message_sha256=hash_message("Override bot"),
    )

    channel_reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {first.id} --channel urgent",
    )
    bot_reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {second.id} --bot alerts",
    )

    assert channel_reply is not None
    assert "published" in channel_reply.lower()
    assert bot_reply is not None
    assert "published" in bot_reply.lower()
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "urgent-channel",
            "message": "Override channel",
            "token": "news-token",
        },
        {
            "id": "post-2",
            "channel_id": "town-channel",
            "message": "Override bot",
            "token": "alerts-token",
        },
    ]
    audits = ctx.audits.list_for_user("alice-id")
    assert [audit.channel_link for audit in audits] == ["town", "urgent"]
    assert [audit.bot_username for audit in audits] == ["alerts-bot", "news-bot"]


async def test_send_without_defaults_fails_safely(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="No default body",
        message_sha256=hash_message("No default body"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!send {draft.id}")

    assert reply is not None
    assert "!default set" in reply
    assert ctx.created_posts == []
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"
    assert ctx.audits.list_for_user("alice-id") == []


async def test_send_with_stale_defaults_fails_safely(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    await dispatch(ctx.make("alice-id", "alice"), "!default set --bot news --channel town")
    ctx.user_bots.soft_delete("alice-id", "news")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Stale default body",
        message_sha256=hash_message("Stale default body"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!send {draft.id}")

    assert reply is not None
    assert "removed" in reply.lower() or "удал" in reply.lower()
    assert ctx.created_posts == []
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"
    assert ctx.audits.list_for_user("alice-id") == []


async def test_fully_explicit_send_works_with_stale_defaults(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["old-token"] = {
        "id": "old-bot-id",
        "username": "old-bot",
        "is_bot": True,
    }
    ctx.token_identities["new-token"] = {
        "id": "new-bot-id",
        "username": "new-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add old old-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add old old-channel")
    await dispatch(ctx.make("alice-id", "alice"), "!default set --bot old --channel old")
    ctx.user_bots.soft_delete("alice-id", "old")
    await dispatch(ctx.make("alice-id", "alice"), "!bot add new new-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add new new-channel")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Explicit survives stale default",
        message_sha256=hash_message("Explicit survives stale default"),
    )

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot new --channel new",
    )

    assert reply is not None
    assert "published" in reply.lower()
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "new-channel",
            "message": "Explicit survives stale default",
            "token": "new-token",
        }
    ]


async def test_send_success_uses_selected_locale(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!lang ru")
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "poster",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Привет",
        message_sha256=hash_message("Привет"),
    )

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel town",
    )

    assert reply == f"Черновик #{draft.id} опубликован."


async def test_send_rejects_foreign_draft(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.upsert_seen_user(user_id="bob-id", username="bob", is_admin=False)
    ctx.users.approve("bob-id", approved_by="admin-id")
    foreign = ctx.post_drafts.create(
        owner_user_id="bob-id",
        message="do not leak this body",
        message_sha256=hash_message("do not leak this body"),
    )

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {foreign.id} --bot news --channel town",
    )

    assert reply is not None
    assert "draft" in reply.lower()
    assert "unavailable" in reply.lower() or "not found" in reply.lower()
    assert "do not leak" not in reply
    assert ctx.created_posts == []
    assert ctx.audits.list_for_user("alice-id") == []


async def test_send_records_failed_audit_on_unknown_channel_alias(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    bot = ctx.user_bots.get_by_owner_and_alias("alice-id", "news")
    message = "Draft stays unpublished"
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message=message,
        message_sha256=hash_message(message),
    )
    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel missing",
    )

    assert reply is not None
    assert "channel" in reply.lower()
    assert ctx.created_posts == []
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"

    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].status == "failed"
    assert audits[0].draft_id == draft.id
    assert audits[0].user_bot_id == bot.id
    assert audits[0].bot_user_id == "bot-id"
    assert audits[0].bot_username == "news-bot"
    assert audits[0].channel_link == "missing"
    assert audits[0].resolved_channel_id is None
    assert audits[0].resolved_team_name is None
    assert audits[0].resolved_channel_name is None
    assert audits[0].message_sha256 == hash_message(message)
    assert audits[0].mattermost_post_id is None
    assert audits[0].error_code == "channel_alias"
    assert audits[0].error_message is not None
    assert "secret-token" not in audits[0].error_message
    assert bot.token_ciphertext not in audits[0].error_message


async def test_send_records_failed_audit_on_post_error(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    message = "Draft stays draft on post failure"
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message=message,
        message_sha256=hash_message(message),
    )
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    ctx.token_post_results[("secret-token", "channel-id")] = MattermostError(403, "denied")

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel town",
    )

    assert reply is not None
    assert "publish" in reply.lower()
    assert ctx.created_posts == []
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"
    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].status == "failed"
    assert audits[0].error_code == "mattermost_post"
    assert audits[0].resolved_channel_id == "channel-id"


async def test_send_rejects_old_channel_link_addressing(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Invalid link body",
        message_sha256=hash_message("Invalid link body"),
    )

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel https://evil.internal/team/channels/town-square",
    )

    assert reply is not None
    assert "channel alias" in reply.lower()
    assert ctx.created_posts == []
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"
    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].status == "failed"
    assert audits[0].error_code == "channel_alias"


async def test_send_rejects_deleted_and_sent_drafts(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    deleted = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="deleted body",
        message_sha256=hash_message("deleted body"),
    )
    sent = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="sent body",
        message_sha256=hash_message("sent body"),
    )
    ctx.post_drafts.soft_delete("alice-id", deleted.id)
    ctx.conn.execute("UPDATE post_draft SET status = 'sent' WHERE id = %s", (sent.id,))

    for draft in (deleted, sent):
        reply = await dispatch(
            ctx.make("alice-id", "alice"),
            f"!send {draft.id} --bot news --channel town",
        )
        assert reply is not None
        assert "unavailable" in reply.lower() or "not found" in reply.lower()
        assert "body" not in reply

    assert ctx.created_posts == []
    assert ctx.audits.list_for_user("alice-id") == []


async def test_send_failure_audit_error_still_returns_safe_reply(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Audit failure body",
        message_sha256=hash_message("Audit failure body"),
    )
    broken_ctx = replace(
        ctx.make("alice-id", "alice"),
        audit_repo=cast(AuditRepo, BrokenAuditRepo()),
    )

    reply = await dispatch(
        broken_ctx,
        f"!send {draft.id} --bot news --channel https://evil.internal/team/channels/town-square",
    )

    assert reply is not None
    assert "channel alias" in reply.lower()
    assert ctx.created_posts == []
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"


async def test_send_success_status_and_audit_are_atomic(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Remote success local audit failure",
        message_sha256=hash_message("Remote success local audit failure"),
    )
    await dispatch(ctx.make("alice-id", "alice"), "!channel add town channel-id")
    broken_ctx = replace(
        ctx.make("alice-id", "alice"),
        audit_repo=cast(AuditRepo, BrokenAuditRepo()),
    )

    reply = await dispatch(
        broken_ctx,
        f"!send {draft.id} --bot news --channel town",
    )

    assert reply is not None
    assert "mattermost accepted" in reply.lower()
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "channel-id",
            "message": "Remote success local audit failure",
            "token": "secret-token",
        }
    ]
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "draft"
    assert ctx.audits.list_for_user("alice-id") == []


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("!send", "usage"),
        ("!send abc --bot news --channel town", "usage"),
        ("!send 1 --bot news --channel town --extra x", "usage"),
        ("!send 1 --bot news --channel", "usage"),
    ],
)
async def test_send_validates_args(ctx: CommandFixture, command: str, expected: str):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), command)

    assert reply is not None
    assert expected in reply.lower()


@pytest.mark.parametrize(
    ("setup_status", "expected"),
    [
        ("pending", "approval"),
        ("blocked", "blocked"),
        (None, "register"),
    ],
)
async def test_send_requires_approved_user(
    ctx: CommandFixture,
    setup_status: str | None,
    expected: str,
):
    if setup_status is not None:
        ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
        if setup_status == "blocked":
            ctx.users.approve("alice-id", approved_by="admin-id")
            ctx.users.block("alice-id", blocked_by="admin-id")

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        "!send 1 --bot news --channel town",
    )

    assert reply is not None
    assert expected in reply.lower()
