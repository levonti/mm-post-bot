from datetime import UTC, datetime, timedelta

import pytest
from testcontainers.postgres import PostgresContainer

from mm_post_bot.db import DbConn, connect_postgres, init_schema
from mm_post_bot.repository import (
    AuditRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserRepo,
)

POSTGRES_IMAGE = "postgres:15-alpine"


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
def repos(pg_conn: DbConn):
    pg_conn.execute("BEGIN")
    yield (
        UserRepo(pg_conn),
        UserBotRepo(pg_conn),
        DraftCaptureRepo(pg_conn),
        PostDraftRepo(pg_conn),
        AuditRepo(pg_conn),
    )
    pg_conn.execute("ROLLBACK")


def test_user_status_lifecycle(repos):
    users, *_ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    assert users.get("u1").status == "pending"

    users.approve("u1", approved_by="admin-id")
    assert users.get("u1").status == "approved"

    users.block("u1", blocked_by="admin-id")
    assert users.get("u1").status == "blocked"

    users.unblock("u1", approved_by="admin-id")
    assert users.get("u1").status == "approved"


def test_admin_is_approved(repos):
    users, *_ = repos
    users.upsert_seen_user(user_id="admin-id", username="admin", is_admin=True)
    admin = users.get("admin-id")
    assert admin.role == "admin"
    assert admin.status == "approved"


def test_user_bot_alias_is_owner_scoped(repos):
    users, bots, *_ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    users.upsert_seen_user(user_id="u2", username="bob", is_admin=False)
    users.approve("u2", approved_by="admin-id")

    first = bots.add(
        owner_user_id="u1",
        alias="news",
        bot_user_id="bot-1",
        bot_username="news-bot",
        bot_display_name="News Bot",
        token_ciphertext="cipher-a",
        token_fingerprint="fp-a",
    )
    second = bots.add(
        owner_user_id="u2",
        alias="news",
        bot_user_id="bot-2",
        bot_username="other-bot",
        bot_display_name=None,
        token_ciphertext="cipher-b",
        token_fingerprint="fp-b",
    )

    assert first.id != second.id
    assert bots.get_by_owner_and_alias("u1", "news").bot_user_id == "bot-1"
    assert bots.get_by_owner_and_alias("u2", "news").bot_user_id == "bot-2"


def test_draft_capture_and_post_draft(repos):
    users, _, captures, drafts, _ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")

    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    captures.start(owner_user_id="u1", expires_at=expires_at)
    assert captures.get_active("u1", now=datetime.now(UTC)) is not None

    draft = drafts.create(owner_user_id="u1", message="hello", message_sha256="hash")
    captures.clear("u1")
    assert drafts.get_for_owner("u1", draft.id).message == "hello"
    assert captures.get_active("u1", now=datetime.now(UTC)) is None


def test_audit_success_row(repos):
    users, bots, _, drafts, audits = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    bot = bots.add(
        owner_user_id="u1",
        alias="news",
        bot_user_id="bot-1",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher",
        token_fingerprint="fp",
    )
    draft = drafts.create(owner_user_id="u1", message="hello", message_sha256="hash")

    audits.record(
        caller_user_id="u1",
        caller_username="alice",
        draft_id=draft.id,
        user_bot_id=bot.id,
        bot_user_id="bot-1",
        bot_username="news-bot",
        channel_link="https://mm.internal/i/team/channels/town-square",
        resolved_channel_id="channel-id",
        resolved_team_name="team",
        resolved_channel_name="town-square",
        message_sha256="hash",
        status="success",
        mattermost_post_id="post-id",
        error_code=None,
        error_message=None,
    )

    rows = audits.list_for_user("u1")
    assert rows[0].status == "success"
    assert rows[0].mattermost_post_id == "post-id"
