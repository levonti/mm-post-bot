from datetime import UTC, datetime, timedelta

import pytest
from psycopg.errors import UniqueViolation
from testcontainers.postgres import PostgresContainer

from mm_post_bot.db import DbConn, connect_postgres, init_schema
from mm_post_bot.repository import (
    AuditRepo,
    DraftAttachmentRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPostDefaultRepo,
    UserPreferenceRepo,
    UserRepo,
    WebLoginTokenRepo,
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
        UserPostDefaultRepo(pg_conn),
        DraftCaptureRepo(pg_conn),
        PostDraftRepo(pg_conn),
        AuditRepo(pg_conn),
    )
    pg_conn.execute("ROLLBACK")


def _approved_user(users: UserRepo, user_id: str, username: str) -> None:
    users.upsert_seen_user(user_id=user_id, username=username, is_admin=False)
    users.approve(user_id, approved_by="admin-id")


def _bot(bots: UserBotRepo, owner_user_id: str, alias: str = "news"):
    return bots.add(
        owner_user_id=owner_user_id,
        alias=alias,
        bot_user_id=f"{alias}-bot-id",
        bot_username=f"{alias}-bot",
        bot_display_name=None,
        token_ciphertext=f"{alias}-cipher",
        token_fingerprint=f"{alias}-fp",
    )


def _channel(channels: UserChannelRepo, owner_user_id: str, alias: str = "town"):
    return channels.add(
        owner_user_id=owner_user_id,
        alias=alias,
        channel_id=f"{alias}-channel",
    )


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
    _approved_user(users, "u1", "alice")
    _approved_user(users, "u2", "bob")

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
    _approved_user(users, "u1", "alice")
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
    _approved_user(users, "u1", "alice")
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
    _approved_user(users, "u1", "alice")
    _approved_user(users, "u2", "bob")

    first = channels.add(owner_user_id="u1", alias="town", channel_id="channel-1")
    second = channels.add(owner_user_id="u2", alias="town", channel_id="channel-2")

    assert first.id != second.id
    assert channels.get_by_owner_and_alias("u1", "town").channel_id == "channel-1"
    assert channels.get_by_owner_and_alias("u2", "town").channel_id == "channel-2"


def test_user_channel_duplicate_active_alias_for_same_owner_raises(repos):
    users, _, channels, *_ = repos
    _approved_user(users, "u1", "alice")
    channels.add(owner_user_id="u1", alias="town", channel_id="channel-1")

    with pytest.raises(UniqueViolation):
        channels.add(owner_user_id="u1", alias="town", channel_id="channel-2")


def test_user_channel_update_list_and_soft_delete(repos):
    users, _, channels, *_ = repos
    _approved_user(users, "u1", "alice")
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


def test_user_post_default_set_get_update_and_clear(repos):
    users, bots, channels, defaults, *_ = repos
    _approved_user(users, "u1", "alice")
    _bot(bots, "u1", "news")
    _channel(channels, "u1", "town")

    created = defaults.set_for_owner("u1", bot_alias="news", channel_alias="town")

    assert created.owner_user_id == "u1"
    assert created.bot.alias == "news"
    assert created.channel.alias == "town"
    assert defaults.get_for_owner("u1") == created
    assert defaults.has_for_owner("u1") is True

    _bot(bots, "u1", "alerts")
    _channel(channels, "u1", "urgent")
    updated = defaults.set_for_owner("u1", bot_alias="alerts", channel_alias="urgent")

    assert updated.bot.alias == "alerts"
    assert updated.channel.alias == "urgent"
    assert updated.updated_at >= created.updated_at

    defaults.clear_for_owner("u1")

    assert defaults.get_for_owner("u1") is None
    assert defaults.has_for_owner("u1") is False


def test_user_post_default_is_owner_scoped(repos):
    users, bots, channels, defaults, *_ = repos
    _approved_user(users, "u1", "alice")
    _approved_user(users, "u2", "bob")
    _bot(bots, "u1", "news")
    _channel(channels, "u1", "town")
    _bot(bots, "u2", "news")
    _channel(channels, "u2", "town")

    first = defaults.set_for_owner("u1", bot_alias="news", channel_alias="town")
    second = defaults.set_for_owner("u2", bot_alias="news", channel_alias="town")

    assert first.owner_user_id == "u1"
    assert second.owner_user_id == "u2"
    assert first.bot.id != second.bot.id
    assert first.channel.id != second.channel.id


def test_user_post_default_tracks_channel_id_updates(repos):
    users, bots, channels, defaults, *_ = repos
    _approved_user(users, "u1", "alice")
    _bot(bots, "u1", "news")
    _channel(channels, "u1", "town")
    defaults.set_for_owner("u1", bot_alias="news", channel_alias="town")

    channels.update_channel_id("u1", "town", channel_id="new-channel-id")

    current = defaults.get_for_owner("u1")
    assert current is not None
    assert current.channel.channel_id == "new-channel-id"


def test_user_post_default_treats_soft_deleted_targets_as_stale(repos):
    users, bots, channels, defaults, *_ = repos
    _approved_user(users, "u1", "alice")
    _bot(bots, "u1", "news")
    _channel(channels, "u1", "town")
    defaults.set_for_owner("u1", bot_alias="news", channel_alias="town")

    bots.soft_delete("u1", "news")

    assert defaults.has_for_owner("u1") is True
    assert defaults.get_for_owner("u1") is None


def test_user_post_default_treats_soft_deleted_channel_as_stale(repos):
    users, bots, channels, defaults, *_ = repos
    _approved_user(users, "u1", "alice")
    _bot(bots, "u1", "news")
    _channel(channels, "u1", "town")
    defaults.set_for_owner("u1", bot_alias="news", channel_alias="town")

    channels.soft_delete("u1", "town")

    assert defaults.has_for_owner("u1") is True
    assert defaults.get_for_owner("u1") is None


def test_draft_capture_and_post_draft(repos):
    users, _, _, _, captures, drafts, _ = repos
    _approved_user(users, "u1", "alice")

    expires_at = datetime.now(UTC) + timedelta(minutes=30)
    captures.start(owner_user_id="u1", expires_at=expires_at)
    assert captures.get_active("u1", now=datetime.now(UTC)) is not None

    draft = drafts.create(owner_user_id="u1", message="hello", message_sha256="hash")
    captures.clear("u1")
    assert drafts.get_for_owner("u1", draft.id).message == "hello"
    assert captures.get_active("u1", now=datetime.now(UTC)) is None


def test_draft_attachment_lifecycle(pg_conn):
    pg_conn.execute("BEGIN")
    try:
        users = UserRepo(pg_conn)
        drafts = PostDraftRepo(pg_conn)
        attachments = DraftAttachmentRepo(pg_conn)
        _approved_user(users, "u-attachment", "attach-user")
        draft = drafts.create(
            owner_user_id="u-attachment",
            message="body",
            message_sha256="hash",
        )

        attachment = attachments.create(
            owner_user_id="u-attachment",
            draft_id=draft.id,
            filename="diagram.png",
            content_type="image/png",
            size_bytes=7,
            data=b"pngdata",
        )

        assert attachment.id > 0
        assert attachment.filename == "diagram.png"
        assert attachment.content_type == "image/png"
        assert attachment.size_bytes == 7
        assert attachment.data == b"pngdata"
        assert attachments.list_for_draft("u-attachment", draft.id) == [attachment]
        assert attachments.get_for_owner("u-attachment", draft.id, attachment.id) == attachment

        attachments.soft_delete("u-attachment", draft.id, attachment.id)

        assert attachments.list_for_draft("u-attachment", draft.id) == []
    finally:
        pg_conn.execute("ROLLBACK")


def test_post_draft_list_only_returns_active_owner_drafts(repos):
    users, _, _, _, _, drafts, _ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    users.upsert_seen_user(user_id="u2", username="bob", is_admin=False)
    users.approve("u2", approved_by="admin-id")
    first = drafts.create(owner_user_id="u1", message="first", message_sha256="hash-1")
    second = drafts.create(owner_user_id="u1", message="second", message_sha256="hash-2")
    drafts.create(owner_user_id="u2", message="other", message_sha256="hash-3")

    assert drafts.list_for_owner("u1") == [second, first]


def test_post_draft_soft_delete_hides_draft(repos):
    users, _, _, _, _, drafts, _ = repos
    users.upsert_seen_user(user_id="u1", username="alice", is_admin=False)
    users.approve("u1", approved_by="admin-id")
    draft = drafts.create(owner_user_id="u1", message="hello", message_sha256="hash")

    drafts.soft_delete("u1", draft.id)

    assert drafts.get_for_owner("u1", draft.id).status == "deleted"
    assert drafts.list_for_owner("u1") == []


def test_post_draft_mark_sent_sets_sent_fields_and_hides_draft(repos):
    users, bots, _, _, _, drafts, _ = repos
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
    users, bots, _, _, _, drafts, audits = repos
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
        channel_link="https://mm.internal/team/channels/town-square",
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


def test_audit_list_for_user_respects_explicit_limit(repos):
    users, bots, _, _, _, drafts, audits = repos
    users.upsert_seen_user(user_id="u-audit-limit", username="auditor", is_admin=False)
    users.approve("u-audit-limit", approved_by="admin-id")
    bot = bots.add(
        owner_user_id="u-audit-limit",
        alias="news",
        bot_user_id="bot-limit",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher",
        token_fingerprint="fp",
    )
    first = drafts.create(owner_user_id="u-audit-limit", message="one", message_sha256="hash-1")
    second = drafts.create(owner_user_id="u-audit-limit", message="two", message_sha256="hash-2")
    for draft in (first, second):
        audits.record(
            caller_user_id="u-audit-limit",
            caller_username="auditor",
            draft_id=draft.id,
            user_bot_id=bot.id,
            bot_user_id="bot-limit",
            bot_username="news-bot",
            channel_link="https://mm.internal/team/channels/town-square",
            resolved_channel_id="channel-id",
            resolved_team_name="team",
            resolved_channel_name="town-square",
            message_sha256=draft.message_sha256,
            status="success",
            mattermost_post_id=f"post-{draft.id}",
            error_code=None,
            error_message=None,
        )

    rows = audits.list_for_user("u-audit-limit", limit=1)

    assert len(rows) == 1


@pytest.mark.parametrize("limit", [0, 101])
def test_audit_list_for_user_rejects_invalid_limit(repos, limit):
    *_, audits = repos

    with pytest.raises(ValueError, match="audit limit must be between 1 and 100"):
        audits.list_for_user("u1", limit=limit)


def test_web_login_token_lifecycle(repos):
    users, *_ = repos
    _approved_user(users, "u-web", "webuser")
    token_repo = WebLoginTokenRepo(users._conn)
    now = datetime.now(UTC)

    created = token_repo.create(
        owner_user_id="u-web",
        token_sha256="hash-a",
        expires_at=now + timedelta(minutes=5),
    )

    assert created.owner_user_id == "u-web"
    assert created.token_sha256 == "hash-a"
    assert created.used_at is None
    assert token_repo.get_usable("hash-a", now=now).id == created.id

    token_repo.mark_used(created.id)

    assert token_repo.get_usable("hash-a", now=now) is None


def test_web_login_token_expired_is_not_usable(repos):
    users, *_ = repos
    _approved_user(users, "u-expired", "expired")
    token_repo = WebLoginTokenRepo(users._conn)
    now = datetime.now(UTC)
    token_repo.create(
        owner_user_id="u-expired",
        token_sha256="hash-expired",
        expires_at=now - timedelta(seconds=1),
    )

    assert token_repo.get_usable("hash-expired", now=now) is None


def test_web_login_token_consume_is_one_time(repos):
    users, *_ = repos
    _approved_user(users, "u-consume", "consume")
    token_repo = WebLoginTokenRepo(users._conn)
    now = datetime.now(UTC)
    created = token_repo.create(
        owner_user_id="u-consume",
        token_sha256="hash-consume",
        expires_at=now + timedelta(minutes=5),
    )

    consumed = token_repo.consume("hash-consume", now=now)
    second = token_repo.consume("hash-consume", now=now)

    assert consumed is not None
    assert consumed.id == created.id
    assert consumed.used_at == now
    assert second is None


def test_post_draft_update_message_updates_hash_and_timestamp(repos):
    users, _, _, _, _, drafts, _ = repos
    _approved_user(users, "u-draft", "drafty")
    draft = drafts.create(
        owner_user_id="u-draft",
        message="Old body",
        message_sha256="old-hash",
    )

    updated = drafts.update_message(
        "u-draft",
        draft.id,
        message="New body",
        message_sha256="new-hash",
    )

    assert updated.message == "New body"
    assert updated.message_sha256 == "new-hash"
    assert updated.status == "draft"
    assert updated.updated_at >= draft.updated_at


def test_post_draft_update_message_rejects_sent_draft(repos):
    users, bots, _, _, _, drafts, _ = repos
    _approved_user(users, "u-sent-edit", "sentedit")
    bot = _bot(bots, "u-sent-edit")
    draft = drafts.create(
        owner_user_id="u-sent-edit",
        message="Original body",
        message_sha256="original-hash",
    )
    drafts.mark_sent(
        "u-sent-edit",
        draft.id,
        sent_by_user_bot_id=bot.id,
        sent_channel_id="channel-id",
        mattermost_post_id="post-id",
    )

    with pytest.raises(LookupError, match="editable post_draft not found"):
        drafts.update_message(
            "u-sent-edit",
            draft.id,
            message="Changed body",
            message_sha256="changed-hash",
        )

    stored = drafts.get_for_owner("u-sent-edit", draft.id)
    assert stored.message == "Original body"
    assert stored.message_sha256 == "original-hash"


def test_post_draft_update_message_rejects_deleted_draft(repos):
    users, _, _, _, _, drafts, _ = repos
    _approved_user(users, "u-deleted-edit", "deletededit")
    draft = drafts.create(
        owner_user_id="u-deleted-edit",
        message="Original body",
        message_sha256="original-hash",
    )
    drafts.soft_delete("u-deleted-edit", draft.id)

    with pytest.raises(LookupError, match="editable post_draft not found"):
        drafts.update_message(
            "u-deleted-edit",
            draft.id,
            message="Changed body",
            message_sha256="changed-hash",
        )

    stored = drafts.get_for_owner("u-deleted-edit", draft.id)
    assert stored.message == "Original body"
    assert stored.message_sha256 == "original-hash"
