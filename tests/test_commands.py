from dataclasses import dataclass
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


@dataclass(frozen=True, slots=True)
class CommandFixture:
    conn: DbConn
    users: UserRepo
    user_bots: UserBotRepo
    draft_captures: DraftCaptureRepo
    post_drafts: PostDraftRepo
    audits: AuditRepo
    manager_mm: FakeMM

    def make(
        self,
        caller_user_id: str,
        caller_username: str,
        *,
        admin_usernames: set[str] | frozenset[str] | None = None,
    ) -> CommandContext:
        return CommandContext(
            caller_user_id=caller_user_id,
            caller_username=caller_username,
            channel_id="dm-channel",
            channel_type="D",
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
            token_encryption_key="0" * 44,
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
def ctx(pg_conn: DbConn) -> CommandFixture:
    pg_conn.execute("BEGIN")
    users = UserRepo(pg_conn)
    yield CommandFixture(
        conn=pg_conn,
        users=users,
        user_bots=UserBotRepo(pg_conn),
        draft_captures=DraftCaptureRepo(pg_conn),
        post_drafts=PostDraftRepo(pg_conn),
        audits=AuditRepo(pg_conn),
        manager_mm=FakeMM(),
    )
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
