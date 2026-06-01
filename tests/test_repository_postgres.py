from datetime import UTC, datetime, timedelta

import pytest
from psycopg.errors import UniqueViolation
from testcontainers.postgres import PostgresContainer

from mm_post_bot.db import DbConn, connect_postgres, init_schema
from mm_post_bot.repository import (
    AuditRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPreferenceRepo,
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
        UserChannelRepo(pg_conn),
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


def test_get_by_username_and_list_by_status(repos):
    users, *_ = repos
    users.upsert_seen_user(user_id="u1", username="charlie", is_admin=False)
    users.upsert_seen_user(user_id="u2", username="alice", is_admin=False)
    users.upsert_seen_user(user_id="u3", username="bob", is_admin=False)
    users.approve("u3", approved_by="admin-id")

    assert users.get_by_username("alice").user_id == "u2"
    assert [user.username for user in users.list_by_status()] == ["alice", "bob", "charlie"]
    assert [user.username for user in users.list_by_status("pending")] == ["alice", "charlie"]
    assert [user.username for user in users.list_by_status("approved")] == ["bob"]


def test_user_preference_locale_round_trip_without_registration(pg_conn):
    pg_conn.execute("BEGIN")
    preferences = UserPreferenceRepo(pg_conn)

    try:
        assert preferences.get_locale("new-user-id") is None

        preference = preferences.set_locale("new-user-id", "ru")

        assert preference.user_id == "new-user-id"
        assert preference.locale == "ru"
        assert preferences.get_locale("new-user-id") == "ru"
    finally:
        pg_conn.execute("ROLLBACK")


def test_user_preference_locale_update(pg_conn):
    pg_conn.execute("BEGIN")
    preferences = UserPreferenceRepo(pg_conn)

    try:
        preferences.set_locale("user-id", "ru")
        updated = preferences.set_locale("user-id", "en")

        assert updated.locale == "en"
        assert preferences.get_locale("user-id") == "en"
    finally:
        pg_conn.execute("ROLLBACK")


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


def test_user_bot_duplicate_active_alias_for_same_owner_raises(repos):
    users, bots, *_ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    bots.add(
        owner_user_id="u1",
        alias="news",
        bot_user_id="bot-1",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher-a",
        token_fingerprint="fp-a",
    )

    with pytest.raises(UniqueViolation):
        bots.add(
            owner_user_id="u1",
            alias="news",
            bot_user_id="bot-2",
            bot_username="other-bot",
            bot_display_name=None,
            token_ciphertext="cipher-b",
            token_fingerprint="fp-b",
        )


def test_user_bot_soft_delete_hides_and_allows_alias_reuse(repos):
    users, bots, *_ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    bots.add(
        owner_user_id="u1",
        alias="news",
        bot_user_id="bot-1",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher-a",
        token_fingerprint="fp-a",
    )

    bots.soft_delete("u1", "news")
    assert bots.list_for_owner("u1") == []

    replacement = bots.add(
        owner_user_id="u1",
        alias="news",
        bot_user_id="bot-2",
        bot_username="other-bot",
        bot_display_name=None,
        token_ciphertext="cipher-b",
        token_fingerprint="fp-b",
    )
    assert bots.list_for_owner("u1") == [replacement]
    assert bots.get_by_owner_and_alias("u1", "news").bot_user_id == "bot-2"


def test_user_channel_alias_is_owner_scoped(repos):
    users, _, channels, *_ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    users.upsert_seen_user(user_id="u2", username="bob", is_admin=False)
    users.approve("u2", approved_by="admin-id")

    first = channels.add(owner_user_id="u1", alias="town", channel_id="channel-1")
    second = channels.add(owner_user_id="u2", alias="town", channel_id="channel-2")

    assert first.id != second.id
    assert channels.get_by_owner_and_alias("u1", "town").channel_id == "channel-1"
    assert channels.get_by_owner_and_alias("u2", "town").channel_id == "channel-2"


def test_user_channel_duplicate_active_alias_for_same_owner_raises(repos):
    users, _, channels, *_ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    channels.add(owner_user_id="u1", alias="town", channel_id="channel-1")

    with pytest.raises(UniqueViolation):
        channels.add(owner_user_id="u1", alias="town", channel_id="channel-2")


def test_user_channel_update_list_and_soft_delete(repos):
    users, _, channels, *_ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    channels.add(owner_user_id="u1", alias="town", channel_id="old-channel")
    alerts = channels.add(owner_user_id="u1", alias="alerts", channel_id="alerts-channel")

    updated = channels.update_channel_id("u1", "town", channel_id="new-channel")

    assert updated.channel_id == "new-channel"
    assert [channel.alias for channel in channels.list_for_owner("u1")] == ["alerts", "town"]
    assert channels.get_by_owner_and_alias("u1", "alerts") == alerts

    channels.soft_delete("u1", "town")

    assert [channel.alias for channel in channels.list_for_owner("u1")] == ["alerts"]
    with pytest.raises(LookupError):
        channels.get_by_owner_and_alias("u1", "town")

    replacement = channels.add(owner_user_id="u1", alias="town", channel_id="replacement-channel")
    assert channels.get_by_owner_and_alias("u1", "town") == replacement


def test_draft_capture_and_post_draft(repos):
    users, _, _, captures, drafts, _ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")

    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    captures.start(owner_user_id="u1", expires_at=expires_at)
    assert captures.get_active("u1", now=datetime.now(UTC)) is not None

    draft = drafts.create(owner_user_id="u1", message="hello", message_sha256="hash")
    captures.clear("u1")
    assert drafts.get_for_owner("u1", draft.id).message == "hello"
    assert captures.get_active("u1", now=datetime.now(UTC)) is None


def test_post_draft_list_only_returns_active_owner_drafts(repos):
    users, _, _, _, drafts, _ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    users.upsert_seen_user(user_id="u2", username="bob", is_admin=False)
    users.approve("u2", approved_by="admin-id")
    first = drafts.create(owner_user_id="u1", message="first", message_sha256="hash-1")
    second = drafts.create(owner_user_id="u1", message="second", message_sha256="hash-2")
    drafts.create(owner_user_id="u2", message="other", message_sha256="hash-3")

    assert drafts.list_for_owner("u1") == [second, first]


def test_post_draft_soft_delete_hides_draft(repos):
    users, _, _, _, drafts, _ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    draft = drafts.create(owner_user_id="u1", message="hello", message_sha256="hash")

    drafts.soft_delete("u1", draft.id)

    assert drafts.get_for_owner("u1", draft.id).status == "deleted"
    assert drafts.list_for_owner("u1") == []


def test_post_draft_mark_sent_sets_sent_fields_and_hides_draft(repos):
    users, bots, _, _, drafts, _ = repos
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

    sent = drafts.mark_sent(
        "u1",
        draft.id,
        sent_by_user_bot_id=bot.id,
        sent_channel_id="channel-id",
        mattermost_post_id="post-id",
    )

    assert sent.status == "sent"
    assert sent.sent_at is not None
    assert sent.sent_by_user_bot_id == bot.id
    assert sent.sent_channel_id == "channel-id"
    assert sent.mattermost_post_id == "post-id"
    assert drafts.list_for_owner("u1") == []


def test_audit_success_row(repos):
    users, bots, _, _, drafts, audits = repos
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
