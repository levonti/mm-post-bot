from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any
from uuid import uuid4

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS app_user (
    user_id     TEXT PRIMARY KEY,
    username    TEXT NOT NULL,
    role        TEXT NOT NULL CHECK (role IN ('admin', 'user')),
    status      TEXT NOT NULL CHECK (status IN ('pending', 'approved', 'blocked')),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    approved_at TIMESTAMPTZ,
    approved_by TEXT,
    blocked_at  TIMESTAMPTZ,
    blocked_by  TEXT
);

CREATE TABLE IF NOT EXISTS user_preference (
    user_id    TEXT PRIMARY KEY,
    locale     TEXT NOT NULL CHECK (locale IN ('en', 'ru')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS user_bot (
    id                BIGSERIAL PRIMARY KEY,
    owner_user_id     TEXT NOT NULL REFERENCES app_user(user_id),
    alias             TEXT NOT NULL,
    bot_user_id       TEXT NOT NULL,
    bot_username      TEXT NOT NULL,
    bot_display_name  TEXT,
    token_ciphertext  TEXT NOT NULL,
    token_fingerprint TEXT NOT NULL,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at        TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_bot_owner_alias_active
    ON user_bot(owner_user_id, alias)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_user_bot_owner ON user_bot(owner_user_id);

CREATE TABLE IF NOT EXISTS user_channel (
    id            BIGSERIAL PRIMARY KEY,
    owner_user_id TEXT NOT NULL REFERENCES app_user(user_id),
    alias         TEXT NOT NULL,
    channel_id    TEXT NOT NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    deleted_at    TIMESTAMPTZ
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_user_channel_owner_alias_active
    ON user_channel(owner_user_id, alias)
    WHERE deleted_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_user_channel_owner ON user_channel(owner_user_id);

CREATE TABLE IF NOT EXISTS draft_capture (
    owner_user_id TEXT PRIMARY KEY REFERENCES app_user(user_id),
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at    TIMESTAMPTZ NOT NULL
);

CREATE TABLE IF NOT EXISTS post_draft (
    id                  BIGSERIAL PRIMARY KEY,
    owner_user_id       TEXT NOT NULL REFERENCES app_user(user_id),
    message             TEXT NOT NULL,
    message_sha256      TEXT NOT NULL,
    status              TEXT NOT NULL CHECK (status IN ('draft', 'sent', 'deleted')),
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at             TIMESTAMPTZ,
    sent_by_user_bot_id BIGINT REFERENCES user_bot(id),
    sent_channel_id     TEXT,
    mattermost_post_id  TEXT
);
CREATE INDEX IF NOT EXISTS idx_post_draft_owner ON post_draft(owner_user_id, status, created_at);

-- draft_id and user_bot_id stay nullable and non-FK so failed or deleted records remain auditable.
CREATE TABLE IF NOT EXISTS post_audit_log (
    id                    BIGSERIAL PRIMARY KEY,
    caller_user_id         TEXT NOT NULL,
    caller_username        TEXT NOT NULL,
    draft_id               BIGINT,
    user_bot_id            BIGINT,
    bot_user_id            TEXT,
    bot_username           TEXT,
    channel_link           TEXT NOT NULL,
    resolved_channel_id    TEXT,
    resolved_team_name     TEXT,
    resolved_channel_name  TEXT,
    message_sha256         TEXT NOT NULL,
    status                 TEXT NOT NULL CHECK (status IN ('success', 'failed')),
    mattermost_post_id     TEXT,
    error_code             TEXT,
    error_message          TEXT,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_post_audit_user ON post_audit_log(caller_user_id, created_at);
"""


class DbConn:
    def __init__(self, inner: Any) -> None:
        self._inner = inner

    def execute(self, sql: str, params: Any = ()) -> Any:
        return self._inner.execute(sql, params)

    def close(self) -> None:
        self._inner.close()

    def in_transaction(self) -> bool:
        from psycopg.pq import TransactionStatus

        return bool(self._inner.info.transaction_status != TransactionStatus.IDLE)


def connect_postgres(dsn: str) -> DbConn:
    import psycopg
    from psycopg.rows import dict_row

    raw = psycopg.connect(dsn, row_factory=dict_row, autocommit=True)
    return DbConn(raw)


def init_schema(conn: DbConn) -> None:
    conn.execute("BEGIN")
    try:
        with conn._inner.cursor() as cur:
            cur.execute(SCHEMA_SQL)
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


@contextmanager
def transaction(conn: DbConn) -> Iterator[DbConn]:
    if conn.in_transaction():
        savepoint = f"sp_{uuid4().hex}"
        conn.execute(f"SAVEPOINT {savepoint}")
        try:
            yield conn
        except Exception:
            conn.execute(f"ROLLBACK TO SAVEPOINT {savepoint}")
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
            raise
        else:
            conn.execute(f"RELEASE SAVEPOINT {savepoint}")
        return

    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
