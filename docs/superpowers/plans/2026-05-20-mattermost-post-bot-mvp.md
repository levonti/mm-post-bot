# Mattermost Post Bot MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a Python Mattermost manager bot that lets approved users add encrypted bot tokens, prepare draft messages in DM, and send those drafts to Mattermost channel links from a selected bot identity.

**Architecture:** Follow the `mm-bot-manager` reference style: one async process connects to Mattermost WebSocket as the manager bot, routes DM/mention commands through a registry, stores state in PostgreSQL 15, and creates short-lived Mattermost REST clients for user-provided posting tokens. Posting is draft-first: `!draft` captures the next normal DM, and `!send <draft_id> --bot <alias> --channel <link>` publishes it.

**Tech Stack:** Python 3.14, `uv`, `httpx`, `websockets`, `pydantic-settings`, `structlog`, `psycopg[binary]`, `cryptography`, PostgreSQL 15, `pytest`, `pytest-asyncio`, `respx`, `testcontainers[postgres]`, `ruff`, `mypy`.

---

## Scope Check

This plan covers one MVP subsystem: the Mattermost post bot service. It intentionally includes project scaffolding because the repository currently contains only documentation. It does not implement a web UI, scheduled posts, media uploads, draft editing, or Mattermost bot account management.

## File Structure

- Create `pyproject.toml`: package metadata, runtime dependencies, dev dependencies, lint/test config.
- Create `.env.example`: non-secret configuration template without any system-admin Mattermost token.
- Create `Dockerfile`: production image with PostgreSQL driver support.
- Create `docker-compose.yml`: service plus PostgreSQL 15.
- Modify `README.md`: local setup, command cheat sheet, manual smoke test.
- Create `src/mm_post_bot/__init__.py`: package marker.
- Create `src/mm_post_bot/__main__.py`: application entrypoint and wiring.
- Create `src/mm_post_bot/config.py`: settings, derived Mattermost REST/WebSocket URLs, admin username parsing.
- Create `src/mm_post_bot/logging.py`: structured logging setup.
- Create `src/mm_post_bot/db.py`: PostgreSQL connection, schema creation, transaction helper.
- Create `src/mm_post_bot/repository.py`: repositories for users, user bots, draft capture, drafts, and audit log.
- Create `src/mm_post_bot/security.py`: token encryption, decryption, fingerprinting, message hashing.
- Create `src/mm_post_bot/mm_client.py`: Mattermost REST client and API error type.
- Create `src/mm_post_bot/channel_links.py`: parse configured Mattermost channel links.
- Create `src/mm_post_bot/ws_listener.py`: WebSocket connection with reconnect.
- Create `src/mm_post_bot/dispatcher.py`: event routing, command redaction, draft capture handling.
- Create `src/mm_post_bot/commands/__init__.py`: command registry and dispatcher.
- Create `src/mm_post_bot/commands/context.py`: command context dataclass.
- Create `src/mm_post_bot/commands/parser.py`: shell-like parser and flags.
- Create `src/mm_post_bot/commands/help.py`: role-aware help.
- Create `src/mm_post_bot/commands/register.py`: registration command.
- Create `src/mm_post_bot/commands/status.py`: user status command.
- Create `src/mm_post_bot/commands/user_admin.py`: approve, block, unblock, list admin commands.
- Create `src/mm_post_bot/commands/bot.py`: add, list, remove user bot commands.
- Create `src/mm_post_bot/commands/draft.py`: draft start, cancel, list, show, delete commands.
- Create `src/mm_post_bot/commands/send.py`: send saved draft command.
- Create `tests/test_config.py`: settings tests.
- Create `tests/test_security.py`: encryption/fingerprint/hash tests.
- Create `tests/test_channel_links.py`: Mattermost channel link parsing tests.
- Create `tests/test_repository_postgres.py`: PostgreSQL schema and repository tests.
- Create `tests/test_mm_client.py`: REST client tests with `respx`.
- Create `tests/test_dispatcher.py`: DM/mention routing and draft capture tests.
- Create `tests/test_commands.py`: command-level behavior tests.

## Task 1: Project Scaffold and Configuration

**Files:**
- Create: `pyproject.toml`
- Create: `.env.example`
- Create: `src/mm_post_bot/__init__.py`
- Create: `src/mm_post_bot/config.py`
- Create: `src/mm_post_bot/logging.py`
- Test: `tests/test_config.py`

- [ ] **Step 1: Write failing settings tests**

Create `tests/test_config.py`:

```python
from mm_post_bot.config import Settings


def test_settings_parse_admins_and_urls():
    settings = Settings(
        mm_url="https://mm.internal/i",
        mm_bot_token="manager-token",
        mm_admins="alice, bob",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key="0" * 44,
    )

    assert settings.admin_usernames == ["alice", "bob"]
    assert settings.mm_rest_base == "https://mm.internal/i/api/v4"
    assert settings.mm_ws_url == "wss://mm.internal/i/api/v4/websocket"


def test_settings_have_no_system_admin_token_field():
    assert "mm_token" not in Settings.model_fields
```

- [ ] **Step 2: Run settings tests to verify failure**

Run:

```bash
uv run pytest tests/test_config.py -q
```

Expected: failure because `pyproject.toml` and `mm_post_bot.config` do not exist.

- [ ] **Step 3: Create project metadata**

Create `pyproject.toml`:

```toml
[project]
name = "mm-post-bot"
version = "0.1.0"
description = "Mattermost post bot with encrypted user bot tokens and draft-based sending."
authors = [{ name = "levonti", email = "leo@badbox.net" }]
requires-python = ">=3.14"
dependencies = [
    "cryptography>=46.0.3",
    "httpx>=0.28.1",
    "psycopg[binary]>=3.2.13",
    "pydantic>=2.13.3",
    "pydantic-settings>=2.14.0",
    "structlog>=25.5.0",
    "websockets>=16.0",
]

[project.scripts]
mm-post-bot = "mm_post_bot.__main__:run"

[build-system]
requires = ["uv_build>=0.11.7,<0.12.0"]
build-backend = "uv_build"

[dependency-groups]
dev = [
    "mypy>=1.20.2",
    "pytest>=9.0.3",
    "pytest-asyncio>=1.3.0",
    "pytest-cov>=7.0.0",
    "respx>=0.23.1",
    "ruff>=0.15.12",
    "testcontainers[postgres]>=4.14.2",
]

[tool.ruff]
line-length = 100
target-version = "py314"

[tool.ruff.lint]
select = ["E", "F", "I", "N", "UP", "B", "SIM", "RUF"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]

[tool.mypy]
python_version = "3.14"
strict = true
files = ["src"]
```

- [ ] **Step 4: Create package and settings**

Create `src/mm_post_bot/__init__.py`:

```python
__all__ = ["__version__"]

__version__ = "0.1.0"
```

Create `src/mm_post_bot/config.py`:

```python
from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    mm_url: HttpUrl = Field(..., description="Base Mattermost URL")
    mm_bot_token: str = Field(..., min_length=1, description="Manager bot PAT")
    mm_admins: str = Field(..., min_length=1, description="Comma-separated admin usernames")
    db_url: str = Field(..., min_length=1, description="PostgreSQL DSN")
    token_encryption_key: str = Field(..., min_length=1, description="Fernet key")
    mm_verify_ssl: bool = Field(default=True)
    log_level: str = Field(default="INFO")

    @property
    def admin_usernames(self) -> list[str]:
        return [u.strip().lstrip("@") for u in self.mm_admins.split(",") if u.strip()]

    @property
    def mm_rest_base(self) -> str:
        return f"{str(self.mm_url).rstrip('/')}/api/v4"

    @property
    def mm_ws_url(self) -> str:
        base = str(self.mm_url).rstrip("/")
        if base.startswith("https://"):
            ws_base = "wss://" + base[len("https://") :]
        elif base.startswith("http://"):
            ws_base = "ws://" + base[len("http://") :]
        else:
            ws_base = base
        return f"{ws_base}/api/v4/websocket"


def load_settings() -> Settings:
    return Settings()  # type: ignore[call-arg]
```

Create `src/mm_post_bot/logging.py`:

```python
import logging
import sys

import structlog


def configure_logging(level: str) -> None:
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    return structlog.get_logger(name)
```

- [ ] **Step 5: Create environment example**

Create `.env.example`:

```dotenv
MM_URL=https://mm.internal/i
MM_BOT_TOKEN=replace-me-manager-bot-token
MM_ADMINS=admin_username
MM_VERIFY_SSL=true
DB_URL=postgresql://mm_post:secret@postgres/mm_post_bot
TOKEN_ENCRYPTION_KEY=replace-with-fernet-key
LOG_LEVEL=INFO

POSTGRES_USER=mm_post
POSTGRES_DB=mm_post_bot
POSTGRES_PASSWORD=secret
```

- [ ] **Step 6: Run settings tests to verify pass**

Run:

```bash
uv sync
uv run pytest tests/test_config.py -q
```

Expected: `2 passed`.

- [ ] **Step 7: Commit scaffold**

```bash
git add pyproject.toml .env.example src/mm_post_bot/__init__.py src/mm_post_bot/config.py src/mm_post_bot/logging.py tests/test_config.py
git commit -m "feat: add project scaffold and settings"
```

## Task 2: Database Schema and Repositories

**Files:**
- Create: `src/mm_post_bot/db.py`
- Create: `src/mm_post_bot/repository.py`
- Test: `tests/test_repository_postgres.py`

- [ ] **Step 1: Write failing repository tests**

Create `tests/test_repository_postgres.py`:

```python
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
```

- [ ] **Step 2: Run repository tests to verify failure**

Run:

```bash
uv run pytest tests/test_repository_postgres.py -q
```

Expected: failure because `db.py` and `repository.py` do not exist.

- [ ] **Step 3: Create PostgreSQL schema helper**

Create `src/mm_post_bot/db.py` with schema for `app_user`, `user_bot`, `draft_capture`, `post_draft`, and `post_audit_log`. Use `BIGSERIAL` primary keys for generated ids, `TIMESTAMPTZ` timestamps, and a partial unique index for active bot aliases:

```python
from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


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
    conn.execute("BEGIN")
    try:
        yield conn
    except Exception:
        conn.execute("ROLLBACK")
        raise
    else:
        conn.execute("COMMIT")
```

- [ ] **Step 4: Create repository dataclasses and methods**

Create `src/mm_post_bot/repository.py` with dataclasses `AppUser`, `UserBot`, `DraftCapture`, `PostDraft`, and `PostAuditRecord`. Implement the methods used by `tests/test_repository_postgres.py`: `UserRepo.upsert_seen_user`, `UserRepo.get`, `UserRepo.approve`, `UserRepo.block`, `UserRepo.unblock`, `UserBotRepo.add`, `UserBotRepo.get_by_owner_and_alias`, `DraftCaptureRepo.start`, `DraftCaptureRepo.get_active`, `DraftCaptureRepo.clear`, `PostDraftRepo.create`, `PostDraftRepo.get_for_owner`, `AuditRepo.record`, and `AuditRepo.list_for_user`.

Use this pattern for row conversion and timestamps:

```python
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

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
```

- [ ] **Step 5: Run repository tests to verify pass**

Run:

```bash
uv run pytest tests/test_repository_postgres.py -q
```

Expected: `5 passed`.

- [ ] **Step 6: Commit database layer**

```bash
git add src/mm_post_bot/db.py src/mm_post_bot/repository.py tests/test_repository_postgres.py
git commit -m "feat: add postgres schema and repositories"
```

## Task 3: Security Helpers and Channel Link Parser

**Files:**
- Create: `src/mm_post_bot/security.py`
- Create: `src/mm_post_bot/channel_links.py`
- Test: `tests/test_security.py`
- Test: `tests/test_channel_links.py`

- [ ] **Step 1: Write failing security tests**

Create `tests/test_security.py`:

```python
from cryptography.fernet import Fernet

from mm_post_bot.security import decrypt_token, encrypt_token, fingerprint_token, hash_message


def test_encrypt_decrypt_roundtrip():
    key = Fernet.generate_key().decode()
    ciphertext = encrypt_token("secret-token", key)

    assert ciphertext != "secret-token"
    assert decrypt_token(ciphertext, key) == "secret-token"


def test_fingerprint_is_stable_and_non_secret():
    first = fingerprint_token("secret-token")
    second = fingerprint_token("secret-token")

    assert first == second
    assert "secret-token" not in first
    assert len(first) == 16


def test_message_hash_is_stable():
    assert hash_message("hello") == hash_message("hello")
    assert hash_message("hello") != hash_message("goodbye")
```

- [ ] **Step 2: Write failing channel link tests**

Create `tests/test_channel_links.py`:

```python
import pytest

from mm_post_bot.channel_links import ChannelLink, ChannelLinkError, parse_channel_link


def test_parse_channel_link_with_subpath():
    parsed = parse_channel_link(
        "https://mm.internal/i/team-name/channels/channel-name",
        mm_url="https://mm.internal/i",
    )

    assert parsed == ChannelLink(team_name="team-name", channel_name="channel-name")


def test_parse_channel_link_rejects_other_host():
    with pytest.raises(ChannelLinkError):
        parse_channel_link(
            "https://evil.internal/i/team-name/channels/channel-name",
            mm_url="https://mm.internal/i",
        )


def test_parse_channel_link_rejects_non_channel_path():
    with pytest.raises(ChannelLinkError):
        parse_channel_link("https://mm.internal/i/team-name/pl/channel-name", mm_url="https://mm.internal/i")
```

- [ ] **Step 3: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_security.py tests/test_channel_links.py -q
```

Expected: failure because `security.py` and `channel_links.py` do not exist.

- [ ] **Step 4: Implement security helpers**

Create `src/mm_post_bot/security.py`:

```python
import hashlib

from cryptography.fernet import Fernet


def encrypt_token(token: str, key: str) -> str:
    return Fernet(key.encode()).encrypt(token.encode()).decode()


def decrypt_token(ciphertext: str, key: str) -> str:
    return Fernet(key.encode()).decrypt(ciphertext.encode()).decode()


def fingerprint_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]


def hash_message(message: str) -> str:
    return hashlib.sha256(message.encode()).hexdigest()
```

- [ ] **Step 5: Implement channel link parser**

Create `src/mm_post_bot/channel_links.py`:

```python
from dataclasses import dataclass
from urllib.parse import urlparse


class ChannelLinkError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class ChannelLink:
    team_name: str
    channel_name: str


def parse_channel_link(link: str, *, mm_url: str) -> ChannelLink:
    base = urlparse(mm_url.rstrip("/"))
    parsed = urlparse(link.strip())
    if parsed.scheme != base.scheme or parsed.netloc != base.netloc:
        raise ChannelLinkError("Channel link must use the configured Mattermost host")

    base_parts = [p for p in base.path.split("/") if p]
    link_parts = [p for p in parsed.path.split("/") if p]
    if base_parts and link_parts[: len(base_parts)] != base_parts:
        raise ChannelLinkError("Channel link must use the configured Mattermost base path")

    parts = link_parts[len(base_parts) :]
    if len(parts) != 3 or parts[1] != "channels":
        raise ChannelLinkError("Expected channel link like https://mm.internal/team/channels/channel")

    return ChannelLink(team_name=parts[0], channel_name=parts[2])
```

- [ ] **Step 6: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_security.py tests/test_channel_links.py -q
```

Expected: `6 passed`.

- [ ] **Step 7: Commit helpers**

```bash
git add src/mm_post_bot/security.py src/mm_post_bot/channel_links.py tests/test_security.py tests/test_channel_links.py
git commit -m "feat: add security helpers and channel link parser"
```

## Task 4: Mattermost REST Client

**Files:**
- Create: `src/mm_post_bot/mm_client.py`
- Test: `tests/test_mm_client.py`

- [ ] **Step 1: Write failing REST client tests**

Create `tests/test_mm_client.py`:

```python
import httpx
import pytest
import respx

from mm_post_bot.mm_client import MattermostClient, MattermostError


@pytest.fixture()
def client():
    return MattermostClient("https://mm.example/api/v4", "test-token")


@respx.mock
async def test_get_me(client):
    respx.get("https://mm.example/api/v4/users/me").mock(
        return_value=httpx.Response(200, json={"id": "u1", "username": "bot", "is_bot": True})
    )

    me = await client.get_me()
    assert me["username"] == "bot"
    await client.aclose()


@respx.mock
async def test_get_channel_by_team_and_name(client):
    route = respx.get(
        "https://mm.example/api/v4/teams/name/team/channels/name/town-square"
    ).mock(return_value=httpx.Response(200, json={"id": "channel-id", "name": "town-square"}))

    channel = await client.get_channel_by_team_and_name("team", "town-square")
    assert channel["id"] == "channel-id"
    assert route.calls.last.request.headers["authorization"] == "Bearer test-token"
    await client.aclose()


@respx.mock
async def test_create_post(client):
    route = respx.post("https://mm.example/api/v4/posts").mock(
        return_value=httpx.Response(201, json={"id": "post-id", "channel_id": "channel-id"})
    )

    post = await client.create_post(channel_id="channel-id", message="hello")
    assert post["id"] == "post-id"
    assert route.calls.last.request.json() == {"channel_id": "channel-id", "message": "hello"}
    await client.aclose()


@respx.mock
async def test_error_surface(client):
    respx.get("https://mm.example/api/v4/users/me").mock(
        return_value=httpx.Response(401, json={"message": "Invalid token"})
    )

    with pytest.raises(MattermostError) as exc:
        await client.get_me()

    assert exc.value.status == 401
    assert "Invalid token" in str(exc.value)
    await client.aclose()
```

- [ ] **Step 2: Run tests to verify failure**

Run:

```bash
uv run pytest tests/test_mm_client.py -q
```

Expected: failure because `mm_client.py` does not exist.

- [ ] **Step 3: Implement REST client**

Create `src/mm_post_bot/mm_client.py`:

```python
from types import TracebackType
from typing import Any, Self

import httpx


class MattermostError(RuntimeError):
    def __init__(self, status: int, message: str, payload: Any = None) -> None:
        super().__init__(f"Mattermost API error {status}: {message}")
        self.status = status
        self.payload = payload


class MattermostClient:
    def __init__(
        self,
        rest_base: str,
        token: str,
        *,
        timeout: float = 15.0,
        verify_ssl: bool = True,
    ) -> None:
        self._client = httpx.AsyncClient(
            base_url=rest_base,
            headers={"Authorization": f"Bearer {token}"},
            timeout=timeout,
            verify=verify_ssl,
        )

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        await self._client.aclose()

    async def _request(self, method: str, path: str, *, json: Any | None = None) -> Any:
        response = await self._client.request(method, path, json=json)
        if response.status_code >= 400:
            try:
                payload = response.json()
                message = payload.get("message", response.text)
            except ValueError:
                payload = None
                message = response.text
            raise MattermostError(response.status_code, message, payload)
        if response.status_code == 204 or not response.content:
            return None
        return response.json()

    async def get_me(self) -> dict[str, Any]:
        return await self._request("GET", "/users/me")  # type: ignore[no-any-return]

    async def create_direct_channel(self, user_id_a: str, user_id_b: str) -> dict[str, Any]:
        return await self._request("POST", "/channels/direct", json=[user_id_a, user_id_b])  # type: ignore[no-any-return]

    async def get_channel_by_team_and_name(
        self,
        team_name: str,
        channel_name: str,
    ) -> dict[str, Any]:
        return await self._request(  # type: ignore[no-any-return]
            "GET",
            f"/teams/name/{team_name}/channels/name/{channel_name}",
        )

    async def create_post(self, *, channel_id: str, message: str) -> dict[str, Any]:
        return await self._request(  # type: ignore[no-any-return]
            "POST",
            "/posts",
            json={"channel_id": channel_id, "message": message},
        )
```

- [ ] **Step 4: Run tests to verify pass**

Run:

```bash
uv run pytest tests/test_mm_client.py -q
```

Expected: `4 passed`.

- [ ] **Step 5: Commit REST client**

```bash
git add src/mm_post_bot/mm_client.py tests/test_mm_client.py
git commit -m "feat: add mattermost rest client"
```

## Task 5: WebSocket Listener and Message Dispatcher

**Files:**
- Create: `src/mm_post_bot/ws_listener.py`
- Create: `src/mm_post_bot/dispatcher.py`
- Create: `src/mm_post_bot/commands/context.py`
- Create: `src/mm_post_bot/commands/parser.py`
- Create: `src/mm_post_bot/commands/__init__.py`
- Test: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing dispatcher tests**

Create `tests/test_dispatcher.py`:

```python
from datetime import UTC, datetime, timedelta

from mm_post_bot.dispatcher import MessageRouter, redact_command_for_log


def test_dm_is_command():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "!help"}, "D") == "!help"


def test_channel_mention_is_command():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "@postbot !status"}, "O") == "!status"


def test_channel_without_mention_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "!status"}, "O") is None


def test_self_message_is_ignored():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "mgr", "message": "!help"}, "D") is None


def test_non_command_dm_can_be_draft_body():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_command({"user_id": "u1", "message": "draft body"}, "D") is None
    assert router.extract_draft_body({"user_id": "u1", "message": "draft body"}, "D") == "draft body"


def test_draft_body_only_in_dm():
    router = MessageRouter(manager_user_id="mgr", manager_username="postbot")
    assert router.extract_draft_body({"user_id": "u1", "message": "draft body"}, "O") is None


def test_redacts_bot_add_token():
    assert redact_command_for_log("!bot add news secret-token") == "!bot add news [REDACTED]"
```

- [ ] **Step 2: Run dispatcher tests to verify failure**

Run:

```bash
uv run pytest tests/test_dispatcher.py -q
```

Expected: failure because dispatcher files do not exist.

- [ ] **Step 3: Implement WebSocket listener**

Create `src/mm_post_bot/ws_listener.py` by following the reference project: connect to `settings.mm_ws_url`, send `authentication_challenge` with `MM_BOT_TOKEN`, yield decoded JSON events, and reconnect with exponential backoff from 1 to 30 seconds.

- [ ] **Step 4: Implement parser and command context**

Create `src/mm_post_bot/commands/parser.py` with `parse_command` using `shlex.split` and `ParsedArgs.from_argv` for positional args and `--flag value` parsing.

Create `src/mm_post_bot/commands/context.py`:

```python
from dataclasses import dataclass

from ..mm_client import MattermostClient
from ..repository import AuditRepo, DraftCaptureRepo, PostDraftRepo, UserBotRepo, UserRepo


@dataclass(frozen=True, slots=True)
class CommandContext:
    caller_user_id: str
    caller_username: str
    channel_id: str
    channel_type: str | None
    user_repo: UserRepo
    user_bot_repo: UserBotRepo
    draft_capture_repo: DraftCaptureRepo
    post_draft_repo: PostDraftRepo
    audit_repo: AuditRepo
    manager_mm: MattermostClient
    manager_user_id: str
    admin_usernames: frozenset[str]
    mm_rest_base: str
    mm_url: str
    token_encryption_key: str
    mm_verify_ssl: bool
```

- [ ] **Step 5: Implement dispatcher routing**

Create `src/mm_post_bot/dispatcher.py` with `MessageRouter.extract_command`, `MessageRouter.extract_draft_body`, `redact_command_for_log`, `CommandContextFactory`, and `handle_event`. `handle_event` must process `posted` events, dispatch commands that begin with `!`, and pass non-command DM messages to a draft-capture handler that will be implemented in Task 8.

- [ ] **Step 6: Run dispatcher tests to verify pass**

Run:

```bash
uv run pytest tests/test_dispatcher.py -q
```

Expected: `7 passed`.

- [ ] **Step 7: Commit routing layer**

```bash
git add src/mm_post_bot/ws_listener.py src/mm_post_bot/dispatcher.py src/mm_post_bot/commands/context.py src/mm_post_bot/commands/parser.py src/mm_post_bot/commands/__init__.py tests/test_dispatcher.py
git commit -m "feat: add websocket routing and dispatcher"
```

## Task 6: Registration, Status, Help, and Admin Commands

**Files:**
- Create: `src/mm_post_bot/commands/help.py`
- Create: `src/mm_post_bot/commands/register.py`
- Create: `src/mm_post_bot/commands/status.py`
- Create: `src/mm_post_bot/commands/user_admin.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing command tests for registration and admin flow**

Add these tests to `tests/test_commands.py`:

```python
async def test_register_creates_pending_user(ctx):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!register")
    assert "pending" in reply.lower()
    assert ctx.users.get("alice-id").status == "pending"


async def test_admin_registers_as_approved(ctx):
    reply = await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!register")
    assert "approved" in reply.lower()
    assert ctx.users.get("admin-id").role == "admin"


async def test_user_approve_requires_admin(ctx):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    reply = await dispatch(ctx.make("bob-id", "bob"), "!user approve alice")
    assert "admin" in reply.lower()


async def test_admin_can_approve_block_and_unblock(ctx):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    approve = await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!user approve alice")
    assert "approved" in approve.lower()
    assert ctx.users.get("alice-id").status == "approved"

    block = await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!user block alice")
    assert "blocked" in block.lower()
    assert ctx.users.get("alice-id").status == "blocked"

    unblock = await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!user unblock alice")
    assert "approved" in unblock.lower()
    assert ctx.users.get("alice-id").status == "approved"
```

- [ ] **Step 2: Run command tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: failure because command modules and test fixture do not exist.

- [ ] **Step 3: Create command test fixture**

In `tests/test_commands.py`, create a fixture with PostgreSQL repositories from Task 2, a `FakeMM` class with `create_direct_channel` and `create_post`, and a `make()` helper that returns `CommandContext` with caller ids, username, channel id `dm-channel`, channel type `D`, manager id `manager-id`, and configurable `admin_usernames`.

- [ ] **Step 4: Implement command registry**

Create or update `src/mm_post_bot/commands/__init__.py` so `dispatch(ctx, raw_text)` requires `!`, parses command args, and registers:

```python
REGISTRY = {
    ("help",): help_cmd.handle,
    ("register",): register.handle,
    ("status",): status.handle,
    ("user", "approve"): user_admin.approve,
    ("user", "block"): user_admin.block,
    ("user", "unblock"): user_admin.unblock,
    ("user", "list"): user_admin.list_users,
}
```

- [ ] **Step 5: Implement user access helpers in command modules**

In `user_admin.py`, resolve users by username or id using repository lookup. Treat usernames case-sensitively to match Mattermost usernames from events. Use `ctx.admin_usernames` and `ctx.caller_username` for admin authorization.

- [ ] **Step 6: Run registration/admin tests to verify pass**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: registration and admin tests pass.

- [ ] **Step 7: Commit registration commands**

```bash
git add src/mm_post_bot/commands tests/test_commands.py
git commit -m "feat: add registration and admin commands"
```

## Task 7: User Bot Token Commands

**Files:**
- Create: `src/mm_post_bot/commands/bot.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing bot command tests**

Add tests:

```python
async def test_bot_add_requires_approved_user(ctx):
    await dispatch(ctx.make("alice-id", "alice"), "!register")
    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add news token")
    assert "approval" in reply.lower()


async def test_bot_add_requires_dm(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    reply = await dispatch(ctx.make("alice-id", "alice", channel_type="O"), "!bot add news token")
    assert "direct message" in reply.lower()


async def test_bot_add_validates_and_encrypts_token(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {"id": "bot-id", "username": "news-bot", "is_bot": True}

    reply = await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    assert "added" in reply.lower()
    saved = ctx.user_bots.get_by_owner_and_alias("alice-id", "news")
    assert saved.bot_user_id == "bot-id"
    assert saved.token_ciphertext != "secret-token"


async def test_bot_list_and_remove(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {"id": "bot-id", "username": "news-bot", "is_bot": True}
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")

    listed = await dispatch(ctx.make("alice-id", "alice"), "!bot list")
    assert "news" in listed
    assert "secret-token" not in listed

    removed = await dispatch(ctx.make("alice-id", "alice"), "!bot remove news")
    assert "removed" in removed.lower()
```

- [ ] **Step 2: Run bot command tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: failure because bot commands are not registered.

- [ ] **Step 3: Implement bot command module**

Create `src/mm_post_bot/commands/bot.py` with handlers `add`, `list_bots`, and `remove`. `add` must call a dynamic `MattermostClient(ctx.mm_rest_base, token)` to validate `GET /users/me`, encrypt the token with `encrypt_token`, store `fingerprint_token`, and never return the token in replies. In tests, allow the fake client factory in context or monkeypatch the client creation so command tests do not call real Mattermost.

- [ ] **Step 4: Register bot commands**

Update `REGISTRY` with:

```python
("bot", "add"): bot.add,
("bot", "list"): bot.list_bots,
("bot", "remove"): bot.remove,
```

- [ ] **Step 5: Run bot command tests to verify pass**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: bot command tests pass.

- [ ] **Step 6: Commit bot commands**

```bash
git add src/mm_post_bot/commands tests/test_commands.py
git commit -m "feat: add encrypted user bot token commands"
```

## Task 8: Draft Capture and Draft Commands

**Files:**
- Create: `src/mm_post_bot/commands/draft.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/dispatcher.py`
- Test: `tests/test_commands.py`
- Test: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing draft command tests**

Add tests:

```python
async def test_draft_start_and_capture(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    started = await dispatch(ctx.make("alice-id", "alice"), "!draft")
    assert "send the post body" in started.lower()

    saved = await ctx.capture_draft_body("alice-id", "alice", "Hello\n\nworld")
    assert "draft #" in saved.lower()
    drafts = ctx.post_drafts.list_for_owner("alice-id")
    assert drafts[0].message == "Hello\n\nworld"


async def test_draft_cancel(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    await dispatch(ctx.make("alice-id", "alice"), "!draft")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!draft cancel")
    assert "cancelled" in reply.lower()
    assert ctx.draft_captures.get_active("alice-id", now=ctx.now()) is None


async def test_draft_list_show_delete(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    draft = ctx.post_drafts.create(owner_user_id="alice-id", message="Hello", message_sha256="hash")

    listed = await dispatch(ctx.make("alice-id", "alice"), "!draft list")
    assert f"#{draft.id}" in listed

    shown = await dispatch(ctx.make("alice-id", "alice"), f"!draft show {draft.id}")
    assert "Hello" in shown

    deleted = await dispatch(ctx.make("alice-id", "alice"), f"!draft delete {draft.id}")
    assert "deleted" in deleted.lower()
```

- [ ] **Step 2: Run draft tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py tests/test_dispatcher.py -q
```

Expected: failure because draft command and capture handler are not implemented.

- [ ] **Step 3: Implement draft command module**

Create `src/mm_post_bot/commands/draft.py` with handlers `start`, `cancel`, `list_drafts`, `show`, and `delete`. `start` inserts or replaces `draft_capture` with `expires_at = now + 30 minutes`. `show` returns the full draft body for the owner. `delete` soft-deletes only owner drafts in `draft` status.

- [ ] **Step 4: Register draft commands**

Update `REGISTRY` with:

```python
("draft",): draft.start,
("draft", "cancel"): draft.cancel,
("draft", "list"): draft.list_drafts,
("draft", "show"): draft.show,
("draft", "delete"): draft.delete,
```

- [ ] **Step 5: Implement non-command DM draft capture**

In `dispatcher.py`, add a function that checks for an active, unexpired `draft_capture` for the sender. If present, save the DM message as `post_draft` with `hash_message(message)`, clear the capture row, and reply with `Draft #<id> saved. Send it with:\n!send <id> --bot <alias> --channel <mattermost-channel-link>`. If no active capture exists, ignore the non-command DM.

- [ ] **Step 6: Run draft tests to verify pass**

Run:

```bash
uv run pytest tests/test_commands.py tests/test_dispatcher.py -q
```

Expected: draft command and capture tests pass.

- [ ] **Step 7: Commit draft flow**

```bash
git add src/mm_post_bot/commands/draft.py src/mm_post_bot/commands/__init__.py src/mm_post_bot/dispatcher.py tests/test_commands.py tests/test_dispatcher.py
git commit -m "feat: add draft capture flow"
```

## Task 9: Send Command and Audit Logging

**Files:**
- Create: `src/mm_post_bot/commands/send.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing send command tests**

Add tests:

```python
async def test_send_posts_saved_draft(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {"id": "bot-id", "username": "news-bot", "is_bot": True}
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    draft = ctx.post_drafts.create(owner_user_id="alice-id", message="Hello", message_sha256="hash")

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel https://mm.internal/i/team/channels/town-square",
    )

    assert "published" in reply.lower()
    assert ctx.created_posts == [{"channel_id": "channel-id", "message": "Hello"}]
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "sent"
    assert ctx.audits.list_for_user("alice-id")[0].status == "success"


async def test_send_rejects_foreign_draft(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.users.upsert_seen_user(user_id="bob-id", username="bob", is_admin=False)
    ctx.users.approve("bob-id", approved_by="admin-id")
    draft = ctx.post_drafts.create(owner_user_id="alice-id", message="Hello", message_sha256="hash")

    reply = await dispatch(ctx.make("bob-id", "bob"), f"!send {draft.id} --bot news --channel https://mm.internal/i/team/channels/town-square")
    assert "draft" in reply.lower()
    assert "not found" in reply.lower()


async def test_send_records_failed_audit_on_channel_error(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {"id": "bot-id", "username": "news-bot", "is_bot": True}
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    ctx.raise_on_channel_lookup = True
    draft = ctx.post_drafts.create(owner_user_id="alice-id", message="Hello", message_sha256="hash")

    reply = await dispatch(
        ctx.make("alice-id", "alice"),
        f"!send {draft.id} --bot news --channel https://mm.internal/i/team/channels/town-square",
    )

    assert "channel" in reply.lower()
    assert ctx.audits.list_for_user("alice-id")[0].status == "failed"
```

- [ ] **Step 2: Run send tests to verify failure**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: failure because send command is not registered.

- [ ] **Step 3: Implement send command**

Create `src/mm_post_bot/commands/send.py`. It must parse `<draft_id>`, `--bot`, and `--channel`; check user status; load owner draft in `draft` status; load owner bot by alias; decrypt token; parse channel link; resolve channel with `MattermostClient.get_channel_by_team_and_name`; create post with draft message; mark draft sent with `sent_by_user_bot_id`, `sent_channel_id`, and `mattermost_post_id`; record success audit. On channel/post errors, record failed audit with a redacted message and leave the draft in `draft` status.

- [ ] **Step 4: Register send command**

Update `REGISTRY` with:

```python
("send",): send.handle,
```

- [ ] **Step 5: Run send tests to verify pass**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: send command tests pass.

- [ ] **Step 6: Commit send flow**

```bash
git add src/mm_post_bot/commands/send.py src/mm_post_bot/commands/__init__.py tests/test_commands.py
git commit -m "feat: add draft send command"
```

## Task 10: Entrypoint, Docker, README, and Full Verification

**Files:**
- Create: `src/mm_post_bot/__main__.py`
- Create: `Dockerfile`
- Create: `docker-compose.yml`
- Modify: `README.md`

- [ ] **Step 1: Implement application entrypoint**

Create `src/mm_post_bot/__main__.py` to load settings, configure logging, connect to PostgreSQL, initialize schema, create repositories, create the manager `MattermostClient`, fetch `get_me()` for the manager bot id and username, create `MessageRouter` and `CommandContextFactory`, stream WebSocket events, and spawn `handle_event` tasks.

- [ ] **Step 2: Create Dockerfile**

Create `Dockerfile`:

```dockerfile
FROM python:3.14-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PROJECT_ENVIRONMENT=/app/.venv \
    PYTHONDONTWRITEBYTECODE=1

RUN pip install --no-cache-dir uv==0.11.7

WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY src ./src
RUN uv sync --frozen --no-dev

FROM python:3.14-slim AS runtime

RUN apt-get update && apt-get install -y --no-install-recommends libpq5 \
    && rm -rf /var/lib/apt/lists/*

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /app/src /app/src

RUN useradd --system --uid 1000 --home /app mmpost
USER mmpost

CMD ["python", "-m", "mm_post_bot"]
```

- [ ] **Step 3: Create Docker Compose**

Create `docker-compose.yml`:

```yaml
services:
  mm-post-bot:
    build: .
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      MM_URL: ${MM_URL}
      MM_BOT_TOKEN: ${MM_BOT_TOKEN}
      MM_ADMINS: ${MM_ADMINS}
      MM_VERIFY_SSL: ${MM_VERIFY_SSL:-true}
      DB_URL: postgresql://${POSTGRES_USER:-mm_post}:${POSTGRES_PASSWORD:-secret}@postgres/${POSTGRES_DB:-mm_post_bot}
      TOKEN_ENCRYPTION_KEY: ${TOKEN_ENCRYPTION_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}

  postgres:
    image: postgres:15-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-mm_post_bot}
      POSTGRES_USER: ${POSTGRES_USER:-mm_post}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-secret}
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-mm_post} -d ${POSTGRES_DB:-mm_post_bot}"]
      interval: 5s
      timeout: 5s
      retries: 5

volumes:
  pgdata:
```

- [ ] **Step 4: Update README**

Replace `README.md` with sections for purpose, Mattermost setup, config, local run, Docker run, command cheat sheet, security notes, and manual smoke test. Include these commands:

```text
!register
!status
!bot add <alias> <token>
!bot list
!bot remove <alias>
!draft
!draft cancel
!draft list
!draft show <draft_id>
!draft delete <draft_id>
!send <draft_id> --bot <alias> --channel <mattermost-channel-link>
!user approve <username-or-user_id>
!user block <username-or-user_id>
!user unblock <username-or-user_id>
!user list [pending|approved|blocked]
```

- [ ] **Step 5: Run static and unit verification**

Run:

```bash
uv lock
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
```

Expected: all commands pass.

- [ ] **Step 6: Run manual local smoke test against Mattermost**

Use `https://mm.internal/i` with a real manager bot token and a real posting bot token:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
cp .env.example .env
docker compose up -d --build
docker compose logs -f mm-post-bot
```

In Mattermost:

```text
!register
!bot add news <existing-bot-token>
!draft
```

Send a normal DM body:

```text
Smoke test from mm-post-bot.
```

Then send:

```text
!send 1 --bot news --channel https://mm.internal/i/<team-name>/channels/<channel-name>
```

Expected: the target channel receives `Smoke test from mm-post-bot.` from the selected bot account.

- [ ] **Step 7: Commit runtime docs and verification fixes**

```bash
git add src/mm_post_bot/__main__.py Dockerfile docker-compose.yml README.md uv.lock
git commit -m "feat: wire runtime and docker setup"
```

## Final Verification

Before opening a PR or marking implementation complete, run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src
uv run pytest -q
git status --short
```

Expected:

- Ruff check passes.
- Ruff format check passes.
- Mypy passes.
- Pytest passes.
- Git status shows only intentional changes or a clean worktree after final commit.
