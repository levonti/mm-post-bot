from dataclasses import dataclass
from importlib.util import find_spec
from typing import Any, cast

import pytest
from testcontainers.postgres import PostgresContainer

from mm_post_bot.commands import CommandContext, dispatch
from mm_post_bot.db import DbConn, connect_postgres, init_schema
from mm_post_bot.mm_client import MattermostClient
from mm_post_bot.repository import AuditRepo, DraftCaptureRepo, PostDraftRepo, UserBotRepo, UserRepo

POSTGRES_IMAGE = "postgres:15-alpine"


class FakeMM:
    async def create_direct_channel(self, user_id_a: str, user_id_b: str) -> dict[str, Any]:
        return {"id": f"dm-{user_id_a}-{user_id_b}"}

    async def create_post(self, channel_id: str, message: str) -> dict[str, Any]:
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
            return TOKEN_IDENTITIES[self.token]
        except KeyError as exc:
            raise AssertionError(f"unexpected token validation for {self.token}") from exc

    async def aclose(self) -> None:
        pass


TOKEN_IDENTITIES: dict[str, dict[str, Any]] = {}
FERNET_KEY = "MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA="


@dataclass(frozen=True, slots=True)
class CommandFixture:
    conn: DbConn
    users: UserRepo
    user_bots: UserBotRepo
    draft_captures: DraftCaptureRepo
    post_drafts: PostDraftRepo
    audits: AuditRepo
    manager_mm: FakeMM
    token_identities: dict[str, dict[str, Any]]

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
            user_bot_repo=self.user_bots,
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
    if find_spec("mm_post_bot.commands.bot") is not None:
        monkeypatch.setattr("mm_post_bot.commands.bot.MattermostClient", FakeTokenMM)

    users = UserRepo(pg_conn)
    yield CommandFixture(
        conn=pg_conn,
        users=users,
        user_bots=UserBotRepo(pg_conn),
        draft_captures=DraftCaptureRepo(pg_conn),
        post_drafts=PostDraftRepo(pg_conn),
        audits=AuditRepo(pg_conn),
        manager_mm=FakeMM(),
        token_identities=TOKEN_IDENTITIES,
    )
    TOKEN_IDENTITIES.clear()
    pg_conn.execute("ROLLBACK")


async def test_register_creates_pending_user(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!register")
    assert reply is not None
    assert "pending" in reply.lower()
    assert ctx.users.get("alice-id").status == "pending"


async def test_admin_registers_as_approved(ctx: CommandFixture):
    reply = await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!register")
    assert reply is not None
    assert "approved" in reply.lower()
    assert ctx.users.get("admin-id").role == "admin"


async def test_user_approve_requires_admin(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    reply = await dispatch(ctx.make("bob-id", "bob"), "!user approve alice")
    assert reply is not None
    assert "admin" in reply.lower()


async def test_admin_can_approve_block_and_unblock(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    admin_ctx = ctx.make("admin-id", "admin", admin_usernames={"admin"})

    approve = await dispatch(admin_ctx, "!user approve alice")
    assert approve is not None
    assert "approved" in approve.lower()
    assert ctx.users.get("alice-id").status == "approved"

    block = await dispatch(admin_ctx, "!user block alice")
    assert block is not None
    assert "blocked" in block.lower()
    assert ctx.users.get("alice-id").status == "blocked"

    unblock = await dispatch(admin_ctx, "!user unblock alice")
    assert unblock is not None
    assert "approved" in unblock.lower()
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
