from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast

from .db import DbConn


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True, slots=True)
class AppUser:
    user_id: str
    username: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
    approved_at: datetime | None
    approved_by: str | None
    blocked_at: datetime | None
    blocked_by: str | None


@dataclass(frozen=True, slots=True)
class UserPreference:
    user_id: str
    locale: str
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class UserBot:
    id: int
    owner_user_id: str
    alias: str
    bot_user_id: str
    bot_username: str
    bot_display_name: str | None
    token_ciphertext: str
    token_fingerprint: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class UserChannel:
    id: int
    owner_user_id: str
    alias: str
    channel_id: str
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None


@dataclass(frozen=True, slots=True)
class UserPostDefault:
    owner_user_id: str
    bot: UserBot
    channel: UserChannel
    created_at: datetime
    updated_at: datetime


@dataclass(frozen=True, slots=True)
class DraftCapture:
    owner_user_id: str
    created_at: datetime
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class PostDraft:
    id: int
    owner_user_id: str
    message: str
    message_sha256: str
    status: str
    created_at: datetime
    updated_at: datetime
    sent_at: datetime | None
    sent_by_user_bot_id: int | None
    sent_channel_id: str | None
    mattermost_post_id: str | None


@dataclass(frozen=True, slots=True)
class PostAuditRecord:
    id: int
    caller_user_id: str
    caller_username: str
    draft_id: int | None
    user_bot_id: int | None
    bot_user_id: str | None
    bot_username: str | None
    channel_link: str
    resolved_channel_id: str | None
    resolved_team_name: str | None
    resolved_channel_name: str | None
    message_sha256: str
    status: str
    mattermost_post_id: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime


def _user_from_row(row: Any) -> AppUser:
    return AppUser(
        user_id=row["user_id"],
        username=row["username"],
        role=row["role"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        approved_at=row["approved_at"],
        approved_by=row["approved_by"],
        blocked_at=row["blocked_at"],
        blocked_by=row["blocked_by"],
    )


def _user_preference_from_row(row: Any) -> UserPreference:
    return UserPreference(
        user_id=row["user_id"],
        locale=row["locale"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _user_bot_from_row(row: Any) -> UserBot:
    return UserBot(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        alias=row["alias"],
        bot_user_id=row["bot_user_id"],
        bot_username=row["bot_username"],
        bot_display_name=row["bot_display_name"],
        token_ciphertext=row["token_ciphertext"],
        token_fingerprint=row["token_fingerprint"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


def _user_channel_from_row(row: Any) -> UserChannel:
    return UserChannel(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        alias=row["alias"],
        channel_id=row["channel_id"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        deleted_at=row["deleted_at"],
    )


def _user_post_default_from_row(row: Any) -> UserPostDefault:
    bot = _user_bot_from_row(
        {
            "id": row["bot_id"],
            "owner_user_id": row["bot_owner_user_id"],
            "alias": row["bot_alias"],
            "bot_user_id": row["bot_user_id"],
            "bot_username": row["bot_username"],
            "bot_display_name": row["bot_display_name"],
            "token_ciphertext": row["bot_token_ciphertext"],
            "token_fingerprint": row["bot_token_fingerprint"],
            "created_at": row["bot_created_at"],
            "updated_at": row["bot_updated_at"],
            "deleted_at": row["bot_deleted_at"],
        }
    )
    channel = _user_channel_from_row(
        {
            "id": row["channel_row_id"],
            "owner_user_id": row["channel_owner_user_id"],
            "alias": row["channel_alias"],
            "channel_id": row["channel_mattermost_id"],
            "created_at": row["channel_created_at"],
            "updated_at": row["channel_updated_at"],
            "deleted_at": row["channel_deleted_at"],
        }
    )
    return UserPostDefault(
        owner_user_id=row["default_owner_user_id"],
        bot=bot,
        channel=channel,
        created_at=row["default_created_at"],
        updated_at=row["default_updated_at"],
    )


def _draft_capture_from_row(row: Any) -> DraftCapture:
    return DraftCapture(
        owner_user_id=row["owner_user_id"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
    )


def _post_draft_from_row(row: Any) -> PostDraft:
    return PostDraft(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        message=row["message"],
        message_sha256=row["message_sha256"],
        status=row["status"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        sent_at=row["sent_at"],
        sent_by_user_bot_id=row["sent_by_user_bot_id"],
        sent_channel_id=row["sent_channel_id"],
        mattermost_post_id=row["mattermost_post_id"],
    )


def _post_audit_from_row(row: Any) -> PostAuditRecord:
    return PostAuditRecord(
        id=row["id"],
        caller_user_id=row["caller_user_id"],
        caller_username=row["caller_username"],
        draft_id=row["draft_id"],
        user_bot_id=row["user_bot_id"],
        bot_user_id=row["bot_user_id"],
        bot_username=row["bot_username"],
        channel_link=row["channel_link"],
        resolved_channel_id=row["resolved_channel_id"],
        resolved_team_name=row["resolved_team_name"],
        resolved_channel_name=row["resolved_channel_name"],
        message_sha256=row["message_sha256"],
        status=row["status"],
        mattermost_post_id=row["mattermost_post_id"],
        error_code=row["error_code"],
        error_message=row["error_message"],
        created_at=row["created_at"],
    )


class UserRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def upsert_seen_user(self, *, user_id: str, username: str, is_admin: bool) -> AppUser:
        role = "admin" if is_admin else "user"
        status = "approved" if is_admin else "pending"
        now = _now()
        approved_at = now if is_admin else None
        row = self._conn.execute(
            """
            INSERT INTO app_user (
                user_id, username, role, status, approved_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                username = EXCLUDED.username,
                role = EXCLUDED.role,
                status = CASE
                    WHEN EXCLUDED.role = 'admin' THEN 'approved'
                    ELSE app_user.status
                END,
                approved_at = CASE
                    WHEN EXCLUDED.role = 'admin'
                        THEN COALESCE(app_user.approved_at, EXCLUDED.approved_at)
                    ELSE app_user.approved_at
                END,
                updated_at = EXCLUDED.updated_at
            RETURNING *
            """,
            (user_id, username, role, status, approved_at, now),
        ).fetchone()
        return _user_from_row(row)

    def get(self, user_id: str) -> AppUser:
        row = self._conn.execute("SELECT * FROM app_user WHERE user_id = %s", (user_id,)).fetchone()
        if row is None:
            raise LookupError(f"app_user not found: {user_id}")
        return _user_from_row(row)

    def get_by_username(self, username: str) -> AppUser:
        row = self._conn.execute(
            """
            SELECT *
            FROM app_user
            WHERE username = %s
            ORDER BY updated_at DESC, user_id ASC
            LIMIT 1
            """,
            (username,),
        ).fetchone()
        if row is None:
            raise LookupError(f"app_user not found: {username}")
        return _user_from_row(row)

    def list_by_status(self, status: str | None = None) -> list[AppUser]:
        if status is None:
            rows = self._conn.execute(
                """
                SELECT *
                FROM app_user
                ORDER BY created_at ASC, username ASC
                """
            ).fetchall()
        else:
            rows = self._conn.execute(
                """
                SELECT *
                FROM app_user
                WHERE status = %s
                ORDER BY created_at ASC, username ASC
                """,
                (status,),
            ).fetchall()
        return [_user_from_row(row) for row in rows]

    def approve(self, user_id: str, *, approved_by: str) -> AppUser:
        now = _now()
        row = self._conn.execute(
            """
            UPDATE app_user
            SET status = 'approved',
                approved_at = %s,
                approved_by = %s,
                blocked_at = NULL,
                blocked_by = NULL,
                updated_at = %s
            WHERE user_id = %s
            RETURNING *
            """,
            (now, approved_by, now, user_id),
        ).fetchone()
        if row is None:
            raise LookupError(f"app_user not found: {user_id}")
        return _user_from_row(row)

    def block(self, user_id: str, *, blocked_by: str) -> AppUser:
        now = _now()
        row = self._conn.execute(
            """
            UPDATE app_user
            SET status = 'blocked',
                blocked_at = %s,
                blocked_by = %s,
                updated_at = %s
            WHERE user_id = %s
            RETURNING *
            """,
            (now, blocked_by, now, user_id),
        ).fetchone()
        if row is None:
            raise LookupError(f"app_user not found: {user_id}")
        return _user_from_row(row)

    def unblock(self, user_id: str, *, approved_by: str) -> AppUser:
        return self.approve(user_id, approved_by=approved_by)


class UserPreferenceRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def get_locale(self, user_id: str) -> str | None:
        row = self._conn.execute(
            "SELECT locale FROM user_preference WHERE user_id = %s",
            (user_id,),
        ).fetchone()
        if row is None:
            return None
        return cast(str, row["locale"])

    def set_locale(self, user_id: str, locale: str) -> UserPreference:
        now = _now()
        row = self._conn.execute(
            """
            INSERT INTO user_preference (user_id, locale, updated_at)
            VALUES (%s, %s, %s)
            ON CONFLICT (user_id) DO UPDATE SET
                locale = EXCLUDED.locale,
                updated_at = EXCLUDED.updated_at
            RETURNING *
            """,
            (user_id, locale, now),
        ).fetchone()
        return _user_preference_from_row(row)


class UserBotRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def add(
        self,
        *,
        owner_user_id: str,
        alias: str,
        bot_user_id: str,
        bot_username: str,
        bot_display_name: str | None,
        token_ciphertext: str,
        token_fingerprint: str,
    ) -> UserBot:
        now = _now()
        row = self._conn.execute(
            """
            INSERT INTO user_bot (
                owner_user_id,
                alias,
                bot_user_id,
                bot_username,
                bot_display_name,
                token_ciphertext,
                token_fingerprint,
                updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                owner_user_id,
                alias,
                bot_user_id,
                bot_username,
                bot_display_name,
                token_ciphertext,
                token_fingerprint,
                now,
            ),
        ).fetchone()
        return _user_bot_from_row(row)

    def get_by_owner_and_alias(self, owner_user_id: str, alias: str) -> UserBot:
        row = self._conn.execute(
            """
            SELECT *
            FROM user_bot
            WHERE owner_user_id = %s
              AND alias = %s
              AND deleted_at IS NULL
            """,
            (owner_user_id, alias),
        ).fetchone()
        if row is None:
            raise LookupError(f"user_bot not found: {owner_user_id}/{alias}")
        return _user_bot_from_row(row)

    def list_for_owner(self, owner_user_id: str) -> list[UserBot]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM user_bot
            WHERE owner_user_id = %s
              AND deleted_at IS NULL
            ORDER BY created_at ASC, alias ASC
            """,
            (owner_user_id,),
        ).fetchall()
        return [_user_bot_from_row(row) for row in rows]

    def soft_delete(self, owner_user_id: str, alias: str) -> None:
        now = _now()
        self._conn.execute(
            """
            UPDATE user_bot
            SET deleted_at = %s,
                updated_at = %s
            WHERE owner_user_id = %s
              AND alias = %s
              AND deleted_at IS NULL
            """,
            (now, now, owner_user_id, alias),
        )


class UserChannelRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def add(self, *, owner_user_id: str, alias: str, channel_id: str) -> UserChannel:
        now = _now()
        row = self._conn.execute(
            """
            INSERT INTO user_channel (
                owner_user_id,
                alias,
                channel_id,
                updated_at
            )
            VALUES (%s, %s, %s, %s)
            RETURNING *
            """,
            (owner_user_id, alias, channel_id, now),
        ).fetchone()
        return _user_channel_from_row(row)

    def update_channel_id(self, owner_user_id: str, alias: str, *, channel_id: str) -> UserChannel:
        now = _now()
        row = self._conn.execute(
            """
            UPDATE user_channel
            SET channel_id = %s,
                updated_at = %s
            WHERE owner_user_id = %s
              AND alias = %s
              AND deleted_at IS NULL
            RETURNING *
            """,
            (channel_id, now, owner_user_id, alias),
        ).fetchone()
        if row is None:
            raise LookupError(f"user_channel not found: {owner_user_id}/{alias}")
        return _user_channel_from_row(row)

    def get_by_owner_and_alias(self, owner_user_id: str, alias: str) -> UserChannel:
        row = self._conn.execute(
            """
            SELECT *
            FROM user_channel
            WHERE owner_user_id = %s
              AND alias = %s
              AND deleted_at IS NULL
            """,
            (owner_user_id, alias),
        ).fetchone()
        if row is None:
            raise LookupError(f"user_channel not found: {owner_user_id}/{alias}")
        return _user_channel_from_row(row)

    def list_for_owner(self, owner_user_id: str) -> list[UserChannel]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM user_channel
            WHERE owner_user_id = %s
              AND deleted_at IS NULL
            ORDER BY created_at ASC, alias ASC
            """,
            (owner_user_id,),
        ).fetchall()
        return [_user_channel_from_row(row) for row in rows]

    def soft_delete(self, owner_user_id: str, alias: str) -> None:
        now = _now()
        self._conn.execute(
            """
            UPDATE user_channel
            SET deleted_at = %s,
                updated_at = %s
            WHERE owner_user_id = %s
              AND alias = %s
              AND deleted_at IS NULL
            """,
            (now, now, owner_user_id, alias),
        )


class UserPostDefaultRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def has_for_owner(self, owner_user_id: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM user_post_default WHERE owner_user_id = %s",
            (owner_user_id,),
        ).fetchone()
        return row is not None

    def get_for_owner(self, owner_user_id: str) -> UserPostDefault | None:
        row = self._conn.execute(
            """
            SELECT
                d.owner_user_id AS default_owner_user_id,
                d.created_at AS default_created_at,
                d.updated_at AS default_updated_at,
                b.id AS bot_id,
                b.owner_user_id AS bot_owner_user_id,
                b.alias AS bot_alias,
                b.bot_user_id AS bot_user_id,
                b.bot_username AS bot_username,
                b.bot_display_name AS bot_display_name,
                b.token_ciphertext AS bot_token_ciphertext,
                b.token_fingerprint AS bot_token_fingerprint,
                b.created_at AS bot_created_at,
                b.updated_at AS bot_updated_at,
                b.deleted_at AS bot_deleted_at,
                c.id AS channel_row_id,
                c.owner_user_id AS channel_owner_user_id,
                c.alias AS channel_alias,
                c.channel_id AS channel_mattermost_id,
                c.created_at AS channel_created_at,
                c.updated_at AS channel_updated_at,
                c.deleted_at AS channel_deleted_at
            FROM user_post_default d
            JOIN user_bot b ON b.id = d.default_user_bot_id
            JOIN user_channel c ON c.id = d.default_user_channel_id
            WHERE d.owner_user_id = %s
              AND b.owner_user_id = d.owner_user_id
              AND c.owner_user_id = d.owner_user_id
              AND b.deleted_at IS NULL
              AND c.deleted_at IS NULL
            """,
            (owner_user_id,),
        ).fetchone()
        if row is None:
            return None
        return _user_post_default_from_row(row)

    def set_for_owner(
        self,
        owner_user_id: str,
        *,
        bot_alias: str,
        channel_alias: str,
    ) -> UserPostDefault:
        now = _now()
        row = self._conn.execute(
            """
            WITH selected_bot AS (
                SELECT id
                FROM user_bot
                WHERE owner_user_id = %s
                  AND alias = %s
                  AND deleted_at IS NULL
            ),
            selected_channel AS (
                SELECT id
                FROM user_channel
                WHERE owner_user_id = %s
                  AND alias = %s
                  AND deleted_at IS NULL
            ),
            upserted AS (
                INSERT INTO user_post_default (
                    owner_user_id,
                    default_user_bot_id,
                    default_user_channel_id,
                    created_at,
                    updated_at
                )
                SELECT %s, selected_bot.id, selected_channel.id, %s, %s
                FROM selected_bot, selected_channel
                ON CONFLICT (owner_user_id) DO UPDATE SET
                    default_user_bot_id = EXCLUDED.default_user_bot_id,
                    default_user_channel_id = EXCLUDED.default_user_channel_id,
                    updated_at = EXCLUDED.updated_at
                RETURNING
                    owner_user_id,
                    created_at,
                    updated_at,
                    default_user_bot_id,
                    default_user_channel_id
            )
            SELECT
                d.owner_user_id AS default_owner_user_id,
                d.created_at AS default_created_at,
                d.updated_at AS default_updated_at,
                b.id AS bot_id,
                b.owner_user_id AS bot_owner_user_id,
                b.alias AS bot_alias,
                b.bot_user_id AS bot_user_id,
                b.bot_username AS bot_username,
                b.bot_display_name AS bot_display_name,
                b.token_ciphertext AS bot_token_ciphertext,
                b.token_fingerprint AS bot_token_fingerprint,
                b.created_at AS bot_created_at,
                b.updated_at AS bot_updated_at,
                b.deleted_at AS bot_deleted_at,
                c.id AS channel_row_id,
                c.owner_user_id AS channel_owner_user_id,
                c.alias AS channel_alias,
                c.channel_id AS channel_mattermost_id,
                c.created_at AS channel_created_at,
                c.updated_at AS channel_updated_at,
                c.deleted_at AS channel_deleted_at
            FROM upserted d
            JOIN user_bot b ON b.id = d.default_user_bot_id
            JOIN user_channel c ON c.id = d.default_user_channel_id
            WHERE b.owner_user_id = d.owner_user_id
              AND c.owner_user_id = d.owner_user_id
            """,
            (owner_user_id, bot_alias, owner_user_id, channel_alias, owner_user_id, now, now),
        ).fetchone()
        if row is None:
            raise LookupError(
                "user_post_default not found: "
                f"{owner_user_id}/{bot_alias}/{channel_alias}"
            )
        return _user_post_default_from_row(row)

    def clear_for_owner(self, owner_user_id: str) -> None:
        self._conn.execute(
            "DELETE FROM user_post_default WHERE owner_user_id = %s",
            (owner_user_id,),
        )


class DraftCaptureRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def start(self, *, owner_user_id: str, expires_at: datetime) -> DraftCapture:
        row = self._conn.execute(
            """
            INSERT INTO draft_capture (owner_user_id, expires_at)
            VALUES (%s, %s)
            ON CONFLICT (owner_user_id) DO UPDATE SET
                created_at = now(),
                expires_at = EXCLUDED.expires_at
            RETURNING *
            """,
            (owner_user_id, expires_at),
        ).fetchone()
        return _draft_capture_from_row(row)

    def get_active(self, owner_user_id: str, *, now: datetime) -> DraftCapture | None:
        row = self._conn.execute(
            """
            SELECT *
            FROM draft_capture
            WHERE owner_user_id = %s
              AND expires_at > %s
            """,
            (owner_user_id, now),
        ).fetchone()
        if row is None:
            return None
        return _draft_capture_from_row(row)

    def clear(self, owner_user_id: str) -> None:
        self._conn.execute("DELETE FROM draft_capture WHERE owner_user_id = %s", (owner_user_id,))


class PostDraftRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    @property
    def conn(self) -> DbConn:
        return self._conn

    def create(self, *, owner_user_id: str, message: str, message_sha256: str) -> PostDraft:
        now = _now()
        row = self._conn.execute(
            """
            INSERT INTO post_draft (owner_user_id, message, message_sha256, status, updated_at)
            VALUES (%s, %s, %s, 'draft', %s)
            RETURNING *
            """,
            (owner_user_id, message, message_sha256, now),
        ).fetchone()
        return _post_draft_from_row(row)

    def get_for_owner(self, owner_user_id: str, draft_id: int) -> PostDraft:
        row = self._conn.execute(
            """
            SELECT *
            FROM post_draft
            WHERE owner_user_id = %s
              AND id = %s
            """,
            (owner_user_id, draft_id),
        ).fetchone()
        if row is None:
            raise LookupError(f"post_draft not found: {owner_user_id}/{draft_id}")
        return _post_draft_from_row(row)

    def list_for_owner(self, owner_user_id: str) -> list[PostDraft]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM post_draft
            WHERE owner_user_id = %s
              AND status = 'draft'
            ORDER BY created_at DESC, id DESC
            """,
            (owner_user_id,),
        ).fetchall()
        return [_post_draft_from_row(row) for row in rows]

    def soft_delete(self, owner_user_id: str, draft_id: int) -> None:
        now = _now()
        self._conn.execute(
            """
            UPDATE post_draft
            SET status = 'deleted',
                updated_at = %s
            WHERE owner_user_id = %s
              AND id = %s
              AND status = 'draft'
            """,
            (now, owner_user_id, draft_id),
        )

    def mark_sent(
        self,
        owner_user_id: str,
        draft_id: int,
        *,
        sent_by_user_bot_id: int,
        sent_channel_id: str,
        mattermost_post_id: str,
    ) -> PostDraft:
        now = _now()
        row = self._conn.execute(
            """
            UPDATE post_draft
            SET status = 'sent',
                sent_at = %s,
                sent_by_user_bot_id = %s,
                sent_channel_id = %s,
                mattermost_post_id = %s,
                updated_at = %s
            WHERE owner_user_id = %s
              AND id = %s
              AND status = 'draft'
            RETURNING *
            """,
            (
                now,
                sent_by_user_bot_id,
                sent_channel_id,
                mattermost_post_id,
                now,
                owner_user_id,
                draft_id,
            ),
        ).fetchone()
        if row is None:
            raise LookupError(f"eligible post_draft not found: {owner_user_id}/{draft_id}")
        return _post_draft_from_row(row)


class AuditRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def record(
        self,
        *,
        caller_user_id: str,
        caller_username: str,
        draft_id: int | None,
        user_bot_id: int | None,
        bot_user_id: str | None,
        bot_username: str | None,
        channel_link: str,
        resolved_channel_id: str | None,
        resolved_team_name: str | None,
        resolved_channel_name: str | None,
        message_sha256: str,
        status: str,
        mattermost_post_id: str | None,
        error_code: str | None,
        error_message: str | None,
    ) -> PostAuditRecord:
        row = self._conn.execute(
            """
            INSERT INTO post_audit_log (
                caller_user_id,
                caller_username,
                draft_id,
                user_bot_id,
                bot_user_id,
                bot_username,
                channel_link,
                resolved_channel_id,
                resolved_team_name,
                resolved_channel_name,
                message_sha256,
                status,
                mattermost_post_id,
                error_code,
                error_message
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING *
            """,
            (
                caller_user_id,
                caller_username,
                draft_id,
                user_bot_id,
                bot_user_id,
                bot_username,
                channel_link,
                resolved_channel_id,
                resolved_team_name,
                resolved_channel_name,
                message_sha256,
                status,
                mattermost_post_id,
                error_code,
                error_message,
            ),
        ).fetchone()
        return _post_audit_from_row(row)

    def list_for_user(self, caller_user_id: str) -> list[PostAuditRecord]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM post_audit_log
            WHERE caller_user_id = %s
            ORDER BY created_at DESC, id DESC
            """,
            (caller_user_id,),
        ).fetchall()
        return [_post_audit_from_row(row) for row in rows]
