# Posting Web UI Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a server-rendered web companion for approved Mattermost users to compose, edit, publish, manage targets, and inspect audit records.

**Architecture:** Add a separate FastAPI/Jinja2 web process that shares the existing PostgreSQL database and posting domain services with the bot. Mattermost remains the identity source: approved users request a one-time `!web` login link in DM, exchange it for a signed HTTP-only web session, and then operate only on their own bots, channels, drafts, defaults, and audit rows. Publishing moves into a shared service so `!send` and web forms use the same target resolution, token decryption, Mattermost API call, draft update, and audit logic.

**Tech Stack:** Python 3.14, FastAPI, Jinja2, Uvicorn, itsdangerous, python-multipart, psycopg, existing `MattermostClient`, existing repository layer, pytest/testcontainers, ruff, mypy.

---

## Scope

This plan implements Phase 2 from `docs/superpowers/specs/2026-06-13-posting-ui-ux-design.md`.

Included:

- `!web` DM command that creates a short-lived one-time login link.
- Signed HTTP-only web sessions and CSRF tokens for state-changing forms.
- Server-rendered web workspace with primary navigation: Composer, Drafts, Targets, Audit.
- Composer for creating a draft, editing unsent drafts, selecting a target, and publishing.
- Drafts list and draft detail actions: open, edit, publish, delete.
- Targets view for bot aliases, channel aliases, default pair, set/clear default, add/remove bot/channel aliases.
- Audit view for read-only send history.
- Shared posting service used by both bot `!send` and web publish routes.
- Docker Compose web service and README/.env documentation.

Excluded:

- Public landing page.
- Mattermost passwords or OAuth.
- Scheduling.
- Mattermost interactive buttons/dialogs.
- Dynamic channel lookup/search in the web UI.

## File Structure

- Modify `pyproject.toml`
  - Add FastAPI, Jinja2, Uvicorn, itsdangerous, python-multipart dependencies.
  - Add script `mm-post-bot-web = "mm_post_bot.web.__main__:run"`.
- Modify `uv.lock`
  - Regenerate through `uv lock`.
- Modify `src/mm_post_bot/config.py`
  - Add web settings: base URL, session secret, cookie security, host, port, token TTL, session max age.
- Modify `src/mm_post_bot/db.py`
  - Add `web_login_token` table.
- Modify `src/mm_post_bot/repository.py`
  - Add `WebLoginToken` dataclass and `WebLoginTokenRepo`.
  - Add `PostDraftRepo.update_message`.
  - Add `AuditRepo.list_for_user(limit: int = 50)`.
- Modify `src/mm_post_bot/commands/context.py`
  - Add `web_login_token_repo`, `web_base_url`, and `web_login_token_ttl_seconds`.
- Modify `src/mm_post_bot/dispatcher.py`
  - Construct `WebLoginTokenRepo` in `CommandContextFactory`.
- Create `src/mm_post_bot/services/__init__.py`
  - Package marker for service modules.
- Create `src/mm_post_bot/services/posting.py`
  - Shared draft, target, and publish service functions.
- Create `src/mm_post_bot/services/web_auth.py`
  - One-time login token generation, hashing, link construction, session signing, CSRF verification.
- Modify `src/mm_post_bot/commands/web.py`
  - Add `!web` command handler.
- Modify `src/mm_post_bot/commands/__init__.py`
  - Register `web`.
- Modify `src/mm_post_bot/commands/help.py`
  - Include `!web`.
- Modify `src/mm_post_bot/commands/send.py`
  - Delegate publishing to `services.posting.publish_draft`.
- Modify `src/mm_post_bot/i18n.py`
  - Add `web.*` command strings and shared publish error strings.
- Create `src/mm_post_bot/web/__init__.py`
  - Web package marker.
- Create `src/mm_post_bot/web/__main__.py`
  - Uvicorn entry point.
- Create `src/mm_post_bot/web/app.py`
  - FastAPI app factory, lifecycle, route registration, exception handlers.
- Create `src/mm_post_bot/web/deps.py`
  - Request dependencies for repositories, current user, CSRF, and flash messages.
- Create `src/mm_post_bot/web/routes.py`
  - HTML routes and form handlers.
- Create `src/mm_post_bot/web/templates/base.html`
  - Base layout and navigation.
- Create `src/mm_post_bot/web/templates/composer.html`
  - Composer page.
- Create `src/mm_post_bot/web/templates/drafts.html`
  - Draft queue page.
- Create `src/mm_post_bot/web/templates/draft_detail.html`
  - Draft review/edit page.
- Create `src/mm_post_bot/web/templates/targets.html`
  - Target settings page.
- Create `src/mm_post_bot/web/templates/audit.html`
  - Audit page.
- Create `src/mm_post_bot/web/static/app.css`
  - Quiet operational UI styling.
- Create `tests/test_web_auth.py`
  - Unit tests for login token lifecycle and session/CSRF helpers.
- Create `tests/test_posting_service.py`
  - Shared publish/draft/target service tests.
- Create `tests/test_web_app.py`
  - FastAPI TestClient route tests.
- Modify `tests/test_commands.py`
  - Add `!web` command coverage and update send expectations if needed.
- Modify `tests/test_repository_postgres.py`
  - Add web token repo and draft update coverage.
- Modify `tests/test_config.py`
  - Add web setting validation.
- Modify `.env.example`
  - Add web env vars.
- Modify `docker-compose.yml`
  - Add `mm-post-bot-web` service.
- Modify `Dockerfile`
  - Keep same image; web process uses the new console script.
- Modify `README.md`
  - Document web UI setup and usage.

## Task 1: Web Configuration, Schema, And Repositories

**Files:**

- Modify: `pyproject.toml`
- Modify: `uv.lock`
- Modify: `src/mm_post_bot/config.py`
- Modify: `src/mm_post_bot/db.py`
- Modify: `src/mm_post_bot/repository.py`
- Modify: `tests/test_config.py`
- Modify: `tests/test_repository_postgres.py`

- [ ] **Step 1: Add failing config tests**

Append to `tests/test_config.py`:

```python
def test_web_settings_defaults_are_local_safe():
    settings = Settings(
        mm_url="https://mm.internal",
        mm_bot_token="manager-token",
        mm_admins="alice",
        db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
        token_encryption_key=VALID_FERNET_KEY,
        web_base_url="http://localhost:8080",
        web_session_secret="x" * 32,
    )

    assert str(settings.web_base_url).rstrip("/") == "http://localhost:8080"
    assert settings.web_host == "0.0.0.0"
    assert settings.web_port == 8080
    assert settings.web_cookie_secure is False
    assert settings.web_login_token_ttl_seconds == 300
    assert settings.web_session_max_age_seconds == 7 * 24 * 60 * 60


def test_web_session_secret_requires_length():
    try:
        Settings(
            mm_url="https://mm.internal",
            mm_bot_token="manager-token",
            mm_admins="alice",
            db_url="postgresql://mm_post:secret@postgres/mm_post_bot",
            token_encryption_key=VALID_FERNET_KEY,
            web_base_url="http://localhost:8080",
            web_session_secret="short",
        )
    except ValueError as exc:
        assert "WEB_SESSION_SECRET must be at least 32 characters" in str(exc)
    else:
        raise AssertionError("short web session secret should be rejected")
```

- [ ] **Step 2: Add failing repository tests**

Append to `tests/test_repository_postgres.py`:

```python
from datetime import UTC, datetime, timedelta


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
```

Also add `WebLoginTokenRepo` to the import list in `tests/test_repository_postgres.py`.

- [ ] **Step 3: Run the tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_config.py::test_web_settings_defaults_are_local_safe tests/test_config.py::test_web_session_secret_requires_length tests/test_repository_postgres.py::test_web_login_token_lifecycle tests/test_repository_postgres.py::test_web_login_token_expired_is_not_usable tests/test_repository_postgres.py::test_post_draft_update_message_updates_hash_and_timestamp -v
```

Expected: failures mention missing settings and missing `WebLoginTokenRepo` / `update_message`.

- [ ] **Step 4: Add dependencies and web script**

Modify `pyproject.toml`:

```toml
dependencies = [
    "cryptography>=46.0.3",
    "fastapi>=0.124.0",
    "httpx>=0.28.1",
    "itsdangerous>=2.2.0",
    "jinja2>=3.1.6",
    "psycopg[binary]>=3.2.13",
    "pydantic>=2.13.3",
    "pydantic-settings>=2.14.0",
    "python-multipart>=0.0.20",
    "structlog>=25.5.0",
    "uvicorn>=0.38.0",
    "websockets>=16.0",
]

[project.scripts]
mm-post-bot = "mm_post_bot.__main__:run"
mm-post-bot-web = "mm_post_bot.web.__main__:run"
```

Run:

```bash
uv lock
```

Expected: `uv.lock` updates without errors.

- [ ] **Step 5: Add web settings**

In `src/mm_post_bot/config.py`, import `SecretStr` and add fields to `Settings`:

```python
from pydantic import Field, HttpUrl, SecretStr, field_validator
```

```python
    web_base_url: HttpUrl = Field(default="http://localhost:8080")
    web_session_secret: SecretStr = Field(..., min_length=32)
    web_cookie_secure: bool = Field(default=False)
    web_host: str = Field(default="0.0.0.0", min_length=1)
    web_port: int = Field(default=8080, ge=1, le=65535)
    web_login_token_ttl_seconds: int = Field(default=300, ge=30, le=3600)
    web_session_max_age_seconds: int = Field(default=7 * 24 * 60 * 60, ge=300)
```

Add this validator:

```python
    @field_validator("web_session_secret")
    @classmethod
    def validate_web_session_secret(cls, value: SecretStr) -> SecretStr:
        if len(value.get_secret_value()) < 32:
            raise ValueError("WEB_SESSION_SECRET must be at least 32 characters")
        return value
```

- [ ] **Step 6: Add schema table**

In `src/mm_post_bot/db.py`, append this SQL before the closing triple quote of `SCHEMA_SQL`:

```sql
CREATE TABLE IF NOT EXISTS web_login_token (
    id             BIGSERIAL PRIMARY KEY,
    owner_user_id  TEXT NOT NULL REFERENCES app_user(user_id),
    token_sha256   TEXT NOT NULL UNIQUE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    expires_at     TIMESTAMPTZ NOT NULL,
    used_at        TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_web_login_token_owner
    ON web_login_token(owner_user_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_web_login_token_usable
    ON web_login_token(token_sha256, expires_at)
    WHERE used_at IS NULL;
```

- [ ] **Step 7: Add repository dataclass and methods**

In `src/mm_post_bot/repository.py`, add the dataclass near `PostAuditRecord`:

```python
@dataclass(frozen=True, slots=True)
class WebLoginToken:
    id: int
    owner_user_id: str
    token_sha256: str
    created_at: datetime
    expires_at: datetime
    used_at: datetime | None
```

Add row mapper near the other mappers:

```python
def _web_login_token_from_row(row: Any) -> WebLoginToken:
    return WebLoginToken(
        id=row["id"],
        owner_user_id=row["owner_user_id"],
        token_sha256=row["token_sha256"],
        created_at=row["created_at"],
        expires_at=row["expires_at"],
        used_at=row["used_at"],
    )
```

Add this repository class before `UserRepo`:

```python
class WebLoginTokenRepo:
    def __init__(self, conn: DbConn) -> None:
        self._conn = conn

    def create(
        self,
        *,
        owner_user_id: str,
        token_sha256: str,
        expires_at: datetime,
    ) -> WebLoginToken:
        row = self._conn.execute(
            """
            INSERT INTO web_login_token (owner_user_id, token_sha256, expires_at)
            VALUES (%s, %s, %s)
            RETURNING *
            """,
            (owner_user_id, token_sha256, expires_at),
        ).fetchone()
        return _web_login_token_from_row(row)

    def get_usable(self, token_sha256: str, *, now: datetime) -> WebLoginToken | None:
        row = self._conn.execute(
            """
            SELECT *
            FROM web_login_token
            WHERE token_sha256 = %s
              AND used_at IS NULL
              AND expires_at > %s
            """,
            (token_sha256, now),
        ).fetchone()
        if row is None:
            return None
        return _web_login_token_from_row(row)

    def mark_used(self, token_id: int) -> None:
        self._conn.execute(
            """
            UPDATE web_login_token
            SET used_at = %s
            WHERE id = %s
              AND used_at IS NULL
            """,
            (_now(), token_id),
        )
```

Add `PostDraftRepo.update_message` after `get_for_owner`:

```python
    def update_message(
        self,
        owner_user_id: str,
        draft_id: int,
        *,
        message: str,
        message_sha256: str,
    ) -> PostDraft:
        now = _now()
        row = self._conn.execute(
            """
            UPDATE post_draft
            SET message = %s,
                message_sha256 = %s,
                updated_at = %s
            WHERE owner_user_id = %s
              AND id = %s
              AND status = 'draft'
            RETURNING *
            """,
            (message, message_sha256, now, owner_user_id, draft_id),
        ).fetchone()
        if row is None:
            raise LookupError(f"editable post_draft not found: {owner_user_id}/{draft_id}")
        return _post_draft_from_row(row)
```

Change `AuditRepo.list_for_user` signature and SQL:

```python
    def list_for_user(self, caller_user_id: str, *, limit: int = 50) -> list[PostAuditRecord]:
        rows = self._conn.execute(
            """
            SELECT *
            FROM post_audit_log
            WHERE caller_user_id = %s
            ORDER BY created_at DESC, id DESC
            LIMIT %s
            """,
            (caller_user_id, limit),
        ).fetchall()
        return [_post_audit_from_row(row) for row in rows]
```

- [ ] **Step 8: Run focused and full verification**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_config.py tests/test_repository_postgres.py -v
uv run ruff check .
uv run mypy
```

Expected: config and repository tests pass; ruff and mypy pass.

- [ ] **Step 9: Commit**

Run:

```bash
git add pyproject.toml uv.lock src/mm_post_bot/config.py src/mm_post_bot/db.py src/mm_post_bot/repository.py tests/test_config.py tests/test_repository_postgres.py
git commit -m "feat: add web configuration and login token storage"
```

Expected: commit succeeds.

## Task 2: Web Auth Service And `!web` Command

**Files:**

- Create: `src/mm_post_bot/services/__init__.py`
- Create: `src/mm_post_bot/services/web_auth.py`
- Create: `src/mm_post_bot/commands/web.py`
- Modify: `src/mm_post_bot/commands/context.py`
- Modify: `src/mm_post_bot/dispatcher.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/commands/help.py`
- Modify: `src/mm_post_bot/i18n.py`
- Create: `tests/test_web_auth.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add failing web auth tests**

Create `tests/test_web_auth.py`:

```python
from datetime import UTC, datetime, timedelta

from itsdangerous import BadSignature

from mm_post_bot.services.web_auth import (
    build_login_url,
    create_login_token,
    csrf_token_for_session,
    hash_login_token,
    load_session,
    sign_session,
    verify_csrf_token,
)


def test_login_token_hash_is_stable_and_secret_is_not_in_hash():
    raw = "raw-token-value"

    digest = hash_login_token(raw)

    assert digest == hash_login_token(raw)
    assert raw not in digest
    assert len(digest) == 64


def test_build_login_url_uses_token_query_param():
    url = build_login_url("https://posts.internal/app/", "abc123")

    assert url == "https://posts.internal/app/login?token=abc123"


def test_create_login_token_stores_hash_and_returns_raw_token(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    now = datetime.now(UTC)

    raw = create_login_token(
        token_repo=ctx.web_login_tokens,
        owner_user_id="alice-id",
        now=now,
        ttl_seconds=300,
    )

    stored = ctx.web_login_tokens.get_usable(hash_login_token(raw), now=now)
    assert stored is not None
    assert stored.owner_user_id == "alice-id"
    assert stored.expires_at >= now + timedelta(seconds=299)


def test_session_sign_and_load_round_trip():
    secret = "s" * 32
    cookie = sign_session(
        secret,
        user_id="alice-id",
        username="alice",
        csrf_nonce="nonce-1",
    )

    session = load_session(secret, cookie, max_age_seconds=60)

    assert session.user_id == "alice-id"
    assert session.username == "alice"
    assert session.csrf_nonce == "nonce-1"


def test_session_rejects_wrong_secret():
    cookie = sign_session(
        "a" * 32,
        user_id="alice-id",
        username="alice",
        csrf_nonce="nonce-1",
    )

    try:
        load_session("b" * 32, cookie, max_age_seconds=60)
    except BadSignature:
        pass
    else:
        raise AssertionError("session signed with another secret should fail")


def test_csrf_token_is_bound_to_session_nonce():
    secret = "s" * 32
    token = csrf_token_for_session(secret, "nonce-1")

    assert verify_csrf_token(secret, "nonce-1", token) is True
    assert verify_csrf_token(secret, "nonce-2", token) is False
```

Add `web_login_tokens: WebLoginTokenRepo` to `CommandFixture` in `tests/test_commands.py`, construct it in the fixture, and import `WebLoginTokenRepo`.

- [ ] **Step 2: Add failing `!web` command tests**

Append to `tests/test_commands.py`:

```python
async def test_web_command_requires_dm(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(
        ctx.make("alice-id", "alice", channel_type="O"),
        "!web",
    )

    assert reply == "Run !web in DM so the login link is private."


async def test_web_command_returns_one_time_login_link(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!web")

    assert reply is not None
    assert "Open web UI:" in reply
    assert "https://posts.internal/login?token=" in reply
    token = reply.split("token=", 1)[1].split()[0]
    assert ctx.web_login_tokens.get_usable(hash_login_token(token), now=datetime.now(UTC)) is not None
```

Also update `CommandFixture.make` to pass:

```python
            web_login_token_repo=self.web_login_tokens,
            web_base_url="https://posts.internal",
            web_login_token_ttl_seconds=300,
```

Import `hash_login_token` from `mm_post_bot.services.web_auth`.

- [ ] **Step 3: Run focused tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_auth.py tests/test_commands.py::test_web_command_requires_dm tests/test_commands.py::test_web_command_returns_one_time_login_link -v
```

Expected: failures mention missing service module, missing context fields, or unknown command.

- [ ] **Step 4: Add `web_auth.py`**

Create `src/mm_post_bot/services/__init__.py` as an empty file.

Create `src/mm_post_bot/services/web_auth.py`:

```python
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from secrets import token_urlsafe
from urllib.parse import urlencode

from itsdangerous import BadSignature, URLSafeTimedSerializer

from ..repository import WebLoginTokenRepo

SESSION_SALT = "mm-post-bot-web-session"
CSRF_SALT = "mm-post-bot-web-csrf"


@dataclass(frozen=True, slots=True)
class WebSession:
    user_id: str
    username: str
    csrf_nonce: str


def hash_login_token(raw_token: str) -> str:
    return sha256(raw_token.encode("utf-8")).hexdigest()


def create_login_token(
    *,
    token_repo: WebLoginTokenRepo,
    owner_user_id: str,
    now: datetime,
    ttl_seconds: int,
) -> str:
    raw_token = token_urlsafe(32)
    token_repo.create(
        owner_user_id=owner_user_id,
        token_sha256=hash_login_token(raw_token),
        expires_at=now + timedelta(seconds=ttl_seconds),
    )
    return raw_token


def build_login_url(web_base_url: str, raw_token: str) -> str:
    base = web_base_url.rstrip("/")
    return f"{base}/login?{urlencode({'token': raw_token})}"


def sign_session(secret: str, *, user_id: str, username: str, csrf_nonce: str) -> str:
    serializer = URLSafeTimedSerializer(secret, salt=SESSION_SALT)
    return serializer.dumps(
        {
            "user_id": user_id,
            "username": username,
            "csrf_nonce": csrf_nonce,
        }
    )


def load_session(secret: str, cookie_value: str, *, max_age_seconds: int) -> WebSession:
    serializer = URLSafeTimedSerializer(secret, salt=SESSION_SALT)
    payload = serializer.loads(cookie_value, max_age=max_age_seconds)
    if not isinstance(payload, dict):
        raise BadSignature("session payload is not an object")
    user_id = payload.get("user_id")
    username = payload.get("username")
    csrf_nonce = payload.get("csrf_nonce")
    if not isinstance(user_id, str) or not user_id:
        raise BadSignature("session payload is missing user_id")
    if not isinstance(username, str) or not username:
        raise BadSignature("session payload is missing username")
    if not isinstance(csrf_nonce, str) or not csrf_nonce:
        raise BadSignature("session payload is missing csrf_nonce")
    return WebSession(user_id=user_id, username=username, csrf_nonce=csrf_nonce)


def csrf_token_for_session(secret: str, csrf_nonce: str) -> str:
    serializer = URLSafeTimedSerializer(secret, salt=CSRF_SALT)
    return serializer.dumps({"csrf_nonce": csrf_nonce})


def verify_csrf_token(secret: str, csrf_nonce: str, token: str) -> bool:
    serializer = URLSafeTimedSerializer(secret, salt=CSRF_SALT)
    try:
        payload = serializer.loads(token, max_age=24 * 60 * 60)
    except BadSignature:
        return False
    return isinstance(payload, dict) and payload.get("csrf_nonce") == csrf_nonce
```

- [ ] **Step 5: Extend command context**

In `src/mm_post_bot/commands/context.py`, import `WebLoginTokenRepo` and add fields to `CommandContext`:

```python
    web_login_token_repo: WebLoginTokenRepo
    web_base_url: str
    web_login_token_ttl_seconds: int
```

In `src/mm_post_bot/dispatcher.py`, import `WebLoginTokenRepo` and pass:

```python
            web_login_token_repo=WebLoginTokenRepo(self._conn),
            web_base_url=str(self._settings.web_base_url).rstrip("/"),
            web_login_token_ttl_seconds=self._settings.web_login_token_ttl_seconds,
```

- [ ] **Step 6: Add `!web` command**

Create `src/mm_post_bot/commands/web.py`:

```python
from datetime import UTC, datetime

from ..services.web_auth import build_login_url, create_login_token
from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    if args.positional or args.flags:
        return ctx.t("web.usage")

    if ctx.channel_type != "D":
        return ctx.t("web.dm_only")

    raw_token = create_login_token(
        token_repo=ctx.web_login_token_repo,
        owner_user_id=ctx.caller_user_id,
        now=datetime.now(UTC),
        ttl_seconds=ctx.web_login_token_ttl_seconds,
    )
    url = build_login_url(ctx.web_base_url, raw_token)
    return ctx.t("web.link", url=url)
```

In `src/mm_post_bot/commands/__init__.py`, import `web` and register:

```python
    "web": web.handle,
```

In `src/mm_post_bot/commands/help.py`, add `!web` to user command text.

In `src/mm_post_bot/i18n.py`, add English keys:

```python
"web.usage": "Usage: !web",
"web.dm_only": "Run !web in DM so the login link is private.",
"web.link": "Open web UI: {url}\nThis link is single-use and expires soon.",
```

Add Russian keys:

```python
"web.usage": "Использование: !web",
"web.dm_only": "Выполните !web в DM, чтобы ссылка входа осталась приватной.",
"web.link": "Открыть web UI: {url}\nСсылка одноразовая и скоро истечёт.",
```

- [ ] **Step 7: Run command and auth tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_auth.py tests/test_commands.py::test_web_command_requires_dm tests/test_commands.py::test_web_command_returns_one_time_login_link -v
uv run pytest -p no:cacheprovider tests/test_i18n.py -v
uv run ruff check .
uv run mypy
```

Expected: all listed tests, ruff, and mypy pass.

- [ ] **Step 8: Commit**

Run:

```bash
git add src/mm_post_bot/services src/mm_post_bot/commands src/mm_post_bot/dispatcher.py src/mm_post_bot/i18n.py tests/test_web_auth.py tests/test_commands.py
git commit -m "feat: add web login command"
```

Expected: commit succeeds.

## Task 3: Shared Posting Service And Bot Send Refactor

**Files:**

- Create: `src/mm_post_bot/services/posting.py`
- Modify: `src/mm_post_bot/commands/send.py`
- Modify: `tests/test_posting_service.py`
- Modify: `tests/test_commands.py`

- [ ] **Step 1: Add failing service tests**

Create `tests/test_posting_service.py`:

```python
from dataclasses import replace

import pytest

from mm_post_bot.commands.context import CommandContext
from mm_post_bot.repository import UserBot, UserChannel
from mm_post_bot.security import encrypt_token, hash_message
from mm_post_bot.services.posting import (
    DraftMessageEmpty,
    PublishDraftRequest,
    TargetRequest,
    create_draft,
    list_target_options,
    publish_draft,
    update_draft_message,
)


def _approved(ctx):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")


def _bot_and_channel(ctx) -> tuple[UserBot, UserChannel]:
    bot = ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext=encrypt_token("secret-token", ctx.make("alice-id", "alice").token_encryption_key),
        token_fingerprint="fp",
    )
    channel = ctx.user_channels.add(
        owner_user_id="alice-id",
        alias="town",
        channel_id="channel-id",
    )
    ctx.user_post_defaults.set_for_owner(
        "alice-id",
        bot_alias=bot.alias,
        channel_alias=channel.alias,
    )
    return bot, channel


def test_create_draft_strips_empty_messages(ctx):
    _approved(ctx)
    command_ctx = ctx.make("alice-id", "alice")

    with pytest.raises(DraftMessageEmpty):
        create_draft(command_ctx, "   \n  ")


def test_create_and_update_draft_hashes_messages(ctx):
    _approved(ctx)
    command_ctx = ctx.make("alice-id", "alice")

    draft = create_draft(command_ctx, "Hello")
    updated = update_draft_message(command_ctx, draft.id, "Updated")

    assert draft.message == "Hello"
    assert draft.message_sha256 == hash_message("Hello")
    assert updated.message == "Updated"
    assert updated.message_sha256 == hash_message("Updated")


def test_list_target_options_marks_default(ctx):
    _approved(ctx)
    _bot_and_channel(ctx)
    command_ctx = ctx.make("alice-id", "alice")

    targets = list_target_options(command_ctx)

    assert [bot.alias for bot in targets.bots] == ["news"]
    assert [channel.alias for channel in targets.channels] == ["town"]
    assert targets.default is not None
    assert targets.default.bot.alias == "news"
    assert targets.default.channel.alias == "town"


async def test_publish_draft_uses_default_target_and_records_audit(ctx):
    _approved(ctx)
    _bot_and_channel(ctx)
    command_ctx = ctx.make("alice-id", "alice")
    draft = create_draft(command_ctx, "Publish me")

    result = await publish_draft(
        command_ctx,
        PublishDraftRequest(
            draft_id=draft.id,
            target=TargetRequest(bot_alias=None, channel_alias=None),
        ),
    )

    assert result.draft_id == draft.id
    assert result.mattermost_post_id == "post-1"
    assert ctx.created_posts == [
        {
            "id": "post-1",
            "channel_id": "channel-id",
            "message": "Publish me",
            "token": "secret-token",
        }
    ]
    audits = ctx.audits.list_for_user("alice-id")
    assert len(audits) == 1
    assert audits[0].status == "success"


async def test_publish_draft_returns_error_when_channel_alias_missing(ctx):
    _approved(ctx)
    _bot_and_channel(ctx)
    command_ctx = ctx.make("alice-id", "alice")
    draft = create_draft(command_ctx, "Publish me")

    with pytest.raises(LookupError):
        await publish_draft(
            command_ctx,
            PublishDraftRequest(
                draft_id=draft.id,
                target=TargetRequest(bot_alias="news", channel_alias="missing"),
            ),
        )
```

- [ ] **Step 2: Run service tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_posting_service.py -v
```

Expected: missing `mm_post_bot.services.posting`.

- [ ] **Step 3: Create shared posting service**

Create `src/mm_post_bot/services/posting.py`:

```python
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any

import httpx

from ..commands.context import CommandContext
from ..db import transaction
from ..mm_client import MattermostClient, MattermostError
from ..repository import PostDraft, UserBot, UserChannel, UserPostDefault
from ..security import decrypt_token, hash_message

_PUBLISH_LOCKS: dict[tuple[str, int], asyncio.Lock] = {}
_PUBLISH_LOCKS_GUARD = asyncio.Lock()


class DraftMessageEmpty(ValueError):
    pass


class PublishError(RuntimeError):
    def __init__(self, code: str, message_key: str) -> None:
        super().__init__(code)
        self.code = code
        self.message_key = message_key


@dataclass(frozen=True, slots=True)
class TargetRequest:
    bot_alias: str | None
    channel_alias: str | None


@dataclass(frozen=True, slots=True)
class TargetOptions:
    bots: list[UserBot]
    channels: list[UserChannel]
    default: UserPostDefault | None
    has_stale_default: bool


@dataclass(frozen=True, slots=True)
class PublishDraftRequest:
    draft_id: int
    target: TargetRequest


@dataclass(frozen=True, slots=True)
class PublishDraftResult:
    draft_id: int
    mattermost_post_id: str
    bot: UserBot
    channel: UserChannel


def _normalized_message(message: str) -> str:
    normalized = message.strip()
    if not normalized:
        raise DraftMessageEmpty("draft message cannot be empty")
    return normalized


def create_draft(ctx: CommandContext, message: str) -> PostDraft:
    normalized = _normalized_message(message)
    return ctx.post_draft_repo.create(
        owner_user_id=ctx.caller_user_id,
        message=normalized,
        message_sha256=hash_message(normalized),
    )


def update_draft_message(ctx: CommandContext, draft_id: int, message: str) -> PostDraft:
    normalized = _normalized_message(message)
    return ctx.post_draft_repo.update_message(
        ctx.caller_user_id,
        draft_id,
        message=normalized,
        message_sha256=hash_message(normalized),
    )


def list_target_options(ctx: CommandContext) -> TargetOptions:
    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    return TargetOptions(
        bots=ctx.user_bot_repo.list_for_owner(ctx.caller_user_id),
        channels=ctx.user_channel_repo.list_for_owner(ctx.caller_user_id),
        default=default,
        has_stale_default=default is None
        and ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id),
    )


async def publish_draft(
    ctx: CommandContext,
    request: PublishDraftRequest,
) -> PublishDraftResult:
    async with _publish_lock(ctx.caller_user_id, request.draft_id):
        return await _publish_draft_locked(ctx, request)


async def _publish_draft_locked(
    ctx: CommandContext,
    request: PublishDraftRequest,
) -> PublishDraftResult:
    try:
        draft = ctx.post_draft_repo.get_for_owner(ctx.caller_user_id, request.draft_id)
    except LookupError as exc:
        raise PublishError("draft_unavailable", "send.draft_unavailable") from exc

    if draft.status != "draft":
        raise PublishError("draft_unavailable", "send.draft_unavailable")

    bot, channel = _resolve_targets(ctx, request.target, draft)
    token = _decrypt_bot_token(ctx, draft, bot, channel)
    mattermost_post_id = await _publish_to_mattermost(ctx, draft, bot, channel, token)
    _mark_sent_and_record_audit(ctx, draft, bot, channel, mattermost_post_id)
    return PublishDraftResult(
        draft_id=draft.id,
        mattermost_post_id=mattermost_post_id,
        bot=bot,
        channel=channel,
    )


@asynccontextmanager
async def _publish_lock(owner_user_id: str, draft_id: int) -> AsyncIterator[None]:
    key = (owner_user_id, draft_id)
    async with _PUBLISH_LOCKS_GUARD:
        lock = _PUBLISH_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _PUBLISH_LOCKS[key] = lock
    await lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _resolve_default(ctx: CommandContext, target: TargetRequest) -> UserPostDefault | None:
    if target.bot_alias is not None and target.channel_alias is not None:
        return None
    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    if default is None:
        if ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id):
            raise PublishError("default_stale", "send.default_stale")
        raise PublishError("defaults_missing", "send.defaults_missing")
    return default


def _resolve_targets(
    ctx: CommandContext,
    target: TargetRequest,
    draft: PostDraft,
) -> tuple[UserBot, UserChannel]:
    default = _resolve_default(ctx, target)
    if target.bot_alias is None:
        if default is None:
            raise PublishError("defaults_missing", "send.defaults_missing")
        bot = default.bot
    else:
        try:
            bot = ctx.user_bot_repo.get_by_owner_and_alias(ctx.caller_user_id, target.bot_alias)
        except LookupError as exc:
            raise PublishError("bot_not_found", "send.bot_not_found") from exc

    if target.channel_alias is None:
        if default is None:
            raise PublishError("defaults_missing", "send.defaults_missing")
        channel = default.channel
    else:
        try:
            channel = ctx.user_channel_repo.get_by_owner_and_alias(
                ctx.caller_user_id,
                target.channel_alias,
            )
        except LookupError as exc:
            _record_failed_audit_safely(
                ctx,
                draft=draft,
                bot=bot,
                channel_alias=target.channel_alias,
                resolved_channel_id=None,
                error_code="channel_alias",
                error_message="Unknown channel alias.",
            )
            raise PublishError("channel_not_found", "send.channel_not_found") from exc

    return bot, channel


def _decrypt_bot_token(
    ctx: CommandContext,
    draft: PostDraft,
    bot: UserBot,
    channel: UserChannel,
) -> str:
    try:
        return decrypt_token(bot.token_ciphertext, ctx.token_encryption_key)
    except Exception as exc:
        _record_failed_audit_safely(
            ctx,
            draft=draft,
            bot=bot,
            channel_alias=channel.alias,
            resolved_channel_id=channel.channel_id,
            error_code="token_decrypt",
            error_message="Bot token storage is misconfigured.",
        )
        raise PublishError("token_decrypt", "send.storage_misconfigured") from exc


async def _publish_to_mattermost(
    ctx: CommandContext,
    draft: PostDraft,
    bot: UserBot,
    channel: UserChannel,
    token: str,
) -> str:
    client = MattermostClient(ctx.mm_rest_base, token, verify_ssl=ctx.mm_verify_ssl)
    try:
        try:
            post_payload = await client.create_post(channel.channel_id, draft.message)
            mattermost_post_id = _string_field(post_payload, "id")
            if mattermost_post_id is None:
                raise ValueError("post response did not include an id")
            return mattermost_post_id
        except (MattermostError, httpx.HTTPError, ValueError) as exc:
            _record_failed_audit_safely(
                ctx,
                draft=draft,
                bot=bot,
                channel_alias=channel.alias,
                resolved_channel_id=channel.channel_id,
                error_code="mattermost_post",
                error_message=_safe_error_message(exc),
            )
            raise PublishError("mattermost_post", "send.publish_failed") from exc
    finally:
        await client.aclose()


def _mark_sent_and_record_audit(
    ctx: CommandContext,
    draft: PostDraft,
    bot: UserBot,
    channel: UserChannel,
    mattermost_post_id: str,
) -> None:
    try:
        with transaction(ctx.post_draft_repo.conn):
            ctx.post_draft_repo.mark_sent(
                ctx.caller_user_id,
                draft.id,
                sent_by_user_bot_id=bot.id,
                sent_channel_id=channel.channel_id,
                mattermost_post_id=mattermost_post_id,
            )
            ctx.audit_repo.record(
                caller_user_id=ctx.caller_user_id,
                caller_username=ctx.caller_username,
                draft_id=draft.id,
                user_bot_id=bot.id,
                bot_user_id=bot.bot_user_id,
                bot_username=bot.bot_username,
                channel_link=channel.alias,
                resolved_channel_id=channel.channel_id,
                resolved_team_name=None,
                resolved_channel_name=None,
                message_sha256=draft.message_sha256,
                status="success",
                mattermost_post_id=mattermost_post_id,
                error_code=None,
                error_message=None,
            )
    except Exception as exc:
        raise PublishError("local_update_failed", "send.local_update_failed") from exc


def _record_failed_audit_safely(
    ctx: CommandContext,
    *,
    draft: PostDraft,
    bot: UserBot,
    channel_alias: str,
    resolved_channel_id: str | None,
    error_code: str,
    error_message: str,
) -> None:
    with suppress(Exception):
        ctx.audit_repo.record(
            caller_user_id=ctx.caller_user_id,
            caller_username=ctx.caller_username,
            draft_id=draft.id,
            user_bot_id=bot.id,
            bot_user_id=bot.bot_user_id,
            bot_username=bot.bot_username,
            channel_link=channel_alias,
            resolved_channel_id=resolved_channel_id,
            resolved_team_name=None,
            resolved_channel_name=None,
            message_sha256=draft.message_sha256,
            status="failed",
            mattermost_post_id=None,
            error_code=error_code,
            error_message=error_message,
        )


def _safe_error_message(exc: BaseException) -> str:
    if isinstance(exc, MattermostError):
        return f"Mattermost API returned {exc.status}."
    if isinstance(exc, httpx.HTTPError):
        return "Mattermost request failed."
    return "Mattermost response was invalid."


def _string_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    return None
```

In `tests/test_posting_service.py`, monkeypatch `mm_post_bot.services.posting.MattermostClient` to `FakeTokenMM` in the existing command fixture or add this to `ctx` fixture in `tests/test_commands.py`:

```python
    if find_spec("mm_post_bot.services.posting") is not None:
        monkeypatch.setattr("mm_post_bot.services.posting.MattermostClient", FakeTokenMM)
```

- [ ] **Step 4: Refactor `send.py` to use the service**

Replace `src/mm_post_bot/commands/send.py` with:

```python
from ..services.posting import (
    PublishDraftRequest,
    PublishError,
    TargetRequest,
    publish_draft,
)
from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    parsed = _parse_args(args)
    if parsed is None:
        return ctx.t("send.usage")

    draft_id, requested_bot_alias, requested_channel_alias = parsed
    try:
        result = await publish_draft(
            ctx,
            PublishDraftRequest(
                draft_id=draft_id,
                target=TargetRequest(
                    bot_alias=requested_bot_alias,
                    channel_alias=requested_channel_alias,
                ),
            ),
        )
    except PublishError as exc:
        return ctx.t(exc.message_key)

    return ctx.t("send.published", draft_id=result.draft_id)


def _parse_args(args: ParsedArgs) -> tuple[int, str | None, str | None] | None:
    if len(args.positional) != 1 or not set(args.flags).issubset({"bot", "channel"}):
        return None

    bot_alias = args.flags.get("bot")
    channel_alias = args.flags.get("channel")
    if bot_alias is not None and (not isinstance(bot_alias, str) or not bot_alias):
        return None
    if channel_alias is not None and (not isinstance(channel_alias, str) or not channel_alias):
        return None

    try:
        draft_id = int(args.positional[0])
    except ValueError:
        return None
    if draft_id <= 0:
        return None

    return draft_id, bot_alias, channel_alias
```

- [ ] **Step 5: Run service and command send tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_posting_service.py tests/test_commands.py -v
uv run ruff check .
uv run mypy
```

Expected: all listed tests, ruff, and mypy pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/mm_post_bot/services/posting.py src/mm_post_bot/commands/send.py tests/test_posting_service.py tests/test_commands.py
git commit -m "feat: share posting service between bot and web"
```

Expected: commit succeeds.

## Task 4: FastAPI App Foundation, Login Exchange, Session, And CSRF

**Files:**

- Create: `src/mm_post_bot/web/__init__.py`
- Create: `src/mm_post_bot/web/__main__.py`
- Create: `src/mm_post_bot/web/app.py`
- Create: `src/mm_post_bot/web/deps.py`
- Create: `src/mm_post_bot/web/routes.py`
- Create: `src/mm_post_bot/web/templates/base.html`
- Create: `src/mm_post_bot/web/static/app.css`
- Create: `tests/test_web_app.py`

- [ ] **Step 1: Add failing app foundation tests**

Create `tests/test_web_app.py`:

```python
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from mm_post_bot.services.web_auth import create_login_token, hash_login_token
from mm_post_bot.web.app import create_app


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


def test_login_requires_valid_token(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    response = client.get("/login?token=bad-token")

    assert response.status_code == 400
    assert "Login link is invalid or expired" in response.text


def test_login_sets_session_cookie_and_redirects(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    _login(client, ctx)

    assert "mmpost_session" in client.cookies


def test_home_requires_session(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/login-required"


def test_home_renders_workspace_after_login(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)

    response = client.get("/")

    assert response.status_code == 200
    assert "Composer" in response.text
    assert "Drafts" in response.text
    assert "Targets" in response.text
    assert "Audit" in response.text
```

Add a `web_settings` fixture in `tests/test_web_app.py`:

```python
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
```

Import `pytest`, `Settings`, and `FERNET_KEY` from `tests.test_commands`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py -v
```

Expected: missing `mm_post_bot.web`.

- [ ] **Step 3: Add web entry point**

Create `src/mm_post_bot/web/__init__.py` as an empty file.

Create `src/mm_post_bot/web/__main__.py`:

```python
import uvicorn

from ..config import load_settings
from ..logging import configure_logging
from .app import create_app_from_settings


def run() -> None:
    settings = load_settings()
    configure_logging(settings.log_level)
    uvicorn.run(
        create_app_from_settings(settings),
        host=settings.web_host,
        port=settings.web_port,
    )


if __name__ == "__main__":
    run()
```

- [ ] **Step 4: Add app factory**

Create `src/mm_post_bot/web/app.py`:

```python
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from ..config import Settings
from ..db import DbConn, connect_postgres, init_schema
from .routes import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    conn = app.state.conn
    try:
        yield
    finally:
        conn.close()


def create_app_from_settings(settings: Settings) -> FastAPI:
    conn = connect_postgres(settings.db_url)
    init_schema(conn)
    return create_app(settings=settings, conn=conn, owns_conn=True)


def create_app(settings: Settings, conn: DbConn, *, owns_conn: bool = False) -> FastAPI:
    app = FastAPI(lifespan=lifespan if owns_conn else None)
    app.state.settings = settings
    app.state.conn = conn
    app.mount("/static", StaticFiles(directory="src/mm_post_bot/web/static"), name="static")
    app.include_router(router)
    return app
```

- [ ] **Step 5: Add dependencies**

Create `src/mm_post_bot/web/deps.py`:

```python
from dataclasses import dataclass

from fastapi import Form, HTTPException, Request
from itsdangerous import BadSignature, SignatureExpired

from ..config import Settings
from ..repository import (
    AuditRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPostDefaultRepo,
    UserRepo,
    WebLoginTokenRepo,
)
from ..services.web_auth import (
    WebSession,
    csrf_token_for_session,
    load_session,
    verify_csrf_token,
)

SESSION_COOKIE = "mmpost_session"


@dataclass(frozen=True, slots=True)
class WebRepos:
    users: UserRepo
    web_login_tokens: WebLoginTokenRepo
    user_bots: UserBotRepo
    user_channels: UserChannelRepo
    user_post_defaults: UserPostDefaultRepo
    post_drafts: PostDraftRepo
    audits: AuditRepo


def settings(request: Request) -> Settings:
    return request.app.state.settings


def repos(request: Request) -> WebRepos:
    conn = request.app.state.conn
    return WebRepos(
        users=UserRepo(conn),
        web_login_tokens=WebLoginTokenRepo(conn),
        user_bots=UserBotRepo(conn),
        user_channels=UserChannelRepo(conn),
        user_post_defaults=UserPostDefaultRepo(conn),
        post_drafts=PostDraftRepo(conn),
        audits=AuditRepo(conn),
    )


def current_session(request: Request) -> WebSession:
    cfg = settings(request)
    cookie_value = request.cookies.get(SESSION_COOKIE)
    if not cookie_value:
        raise HTTPException(status_code=303, headers={"Location": "/login-required"})
    try:
        return load_session(
            cfg.web_session_secret.get_secret_value(),
            cookie_value,
            max_age_seconds=cfg.web_session_max_age_seconds,
        )
    except (BadSignature, SignatureExpired) as exc:
        raise HTTPException(status_code=303, headers={"Location": "/login-required"}) from exc


def csrf_token(request: Request) -> str:
    session = current_session(request)
    cfg = settings(request)
    return csrf_token_for_session(cfg.web_session_secret.get_secret_value(), session.csrf_nonce)


def require_csrf(request: Request, csrf: str = Form(...)) -> None:
    session = current_session(request)
    cfg = settings(request)
    if not verify_csrf_token(cfg.web_session_secret.get_secret_value(), session.csrf_nonce, csrf):
        raise HTTPException(status_code=400, detail="Invalid form token")
```

- [ ] **Step 6: Add base route and login route**

Create `src/mm_post_bot/web/routes.py`:

```python
from datetime import UTC, datetime
from secrets import token_urlsafe

from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from ..services.web_auth import hash_login_token, sign_session
from .deps import SESSION_COOKIE, csrf_token, current_session, repos, settings

router = APIRouter()
templates = Jinja2Templates(directory="src/mm_post_bot/web/templates")


@router.get("/login-required", response_class=HTMLResponse)
async def login_required(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(
        request,
        "base.html",
        {
            "request": request,
            "title": "Login required",
            "session": None,
            "csrf": "",
            "content": "Run !web in Mattermost DM to get a private login link.",
        },
        status_code=401,
    )


@router.get("/login")
async def login(request: Request, token: str) -> Response:
    cfg = settings(request)
    repo_set = repos(request)
    hashed = hash_login_token(token)
    stored = repo_set.web_login_tokens.get_usable(hashed, now=datetime.now(UTC))
    if stored is None:
        raise HTTPException(status_code=400, detail="Login link is invalid or expired")
    user = repo_set.users.get(stored.owner_user_id)
    if user.status != "approved":
        raise HTTPException(status_code=403, detail="User is not approved")
    repo_set.web_login_tokens.mark_used(stored.id)
    cookie_value = sign_session(
        cfg.web_session_secret.get_secret_value(),
        user_id=user.user_id,
        username=user.username,
        csrf_nonce=token_urlsafe(16),
    )
    response = RedirectResponse("/", status_code=303)
    response.set_cookie(
        SESSION_COOKIE,
        cookie_value,
        httponly=True,
        secure=cfg.web_cookie_secure,
        samesite="lax",
        max_age=cfg.web_session_max_age_seconds,
    )
    return response


@router.get("/", response_class=HTMLResponse)
async def home(request: Request) -> HTMLResponse:
    session = current_session(request)
    return templates.TemplateResponse(
        request,
        "composer.html",
        {
            "request": request,
            "title": "Composer",
            "session": session,
            "csrf": csrf_token(request),
            "message": "",
            "bots": [],
            "channels": [],
            "default": None,
            "error": "",
            "notice": "",
        },
    )
```

- [ ] **Step 7: Add base template and CSS**

Create `src/mm_post_bot/web/templates/base.html`:

```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{{ title }} - mm-post-bot</title>
    <link rel="stylesheet" href="/static/app.css">
  </head>
  <body>
    <header class="topbar">
      <div class="brand">mm-post-bot</div>
      {% if session %}
      <nav class="nav" aria-label="Primary">
        <a href="/">Composer</a>
        <a href="/drafts">Drafts</a>
        <a href="/targets">Targets</a>
        <a href="/audit">Audit</a>
      </nav>
      <div class="user">@{{ session.username }}</div>
      {% endif %}
    </header>
    <main class="shell">
      {% if content %}
      <section class="panel">{{ content }}</section>
      {% endif %}
      {% block content %}{% endblock %}
    </main>
  </body>
</html>
```

Create `src/mm_post_bot/web/templates/composer.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="workspace">
  <div class="toolbar">
    <h1>Composer</h1>
    <a class="button secondary" href="/drafts">Drafts</a>
  </div>
  {% if error %}<div class="alert error">{{ error }}</div>{% endif %}
  {% if notice %}<div class="alert notice">{{ notice }}</div>{% endif %}
  <form method="post" action="/drafts" class="composer-form">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label for="message">Post body</label>
    <textarea id="message" name="message" rows="14">{{ message }}</textarea>
    <div class="actions">
      <button type="submit">Save draft</button>
    </div>
  </form>
</section>
{% endblock %}
```

Create `src/mm_post_bot/web/static/app.css`:

```css
:root {
  color-scheme: light;
  --bg: #f7f8fa;
  --panel: #ffffff;
  --text: #1f2933;
  --muted: #637083;
  --line: #d8dee8;
  --accent: #1769aa;
  --accent-strong: #0f568d;
  --danger: #b42318;
  --ok: #1f7a4d;
}

* { box-sizing: border-box; }
body {
  margin: 0;
  font: 14px/1.45 system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
  background: var(--bg);
  color: var(--text);
}
.topbar {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 24px;
  min-height: 56px;
  padding: 0 24px;
  border-bottom: 1px solid var(--line);
  background: var(--panel);
}
.brand { font-weight: 700; }
.nav { display: flex; gap: 8px; }
.nav a, .button, button {
  border: 1px solid var(--line);
  border-radius: 6px;
  background: var(--panel);
  color: var(--text);
  padding: 8px 12px;
  text-decoration: none;
  cursor: pointer;
}
button {
  background: var(--accent);
  color: #ffffff;
  border-color: var(--accent);
}
button:hover { background: var(--accent-strong); }
.secondary { color: var(--muted); }
.user { color: var(--muted); }
.shell {
  width: min(1120px, 100%);
  margin: 0 auto;
  padding: 24px;
}
.workspace, .panel {
  background: var(--panel);
  border: 1px solid var(--line);
  border-radius: 8px;
  padding: 20px;
}
.toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  margin-bottom: 16px;
}
h1 { margin: 0; font-size: 22px; }
label { display: block; margin-bottom: 6px; font-weight: 600; }
textarea, input, select {
  width: 100%;
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px;
  font: inherit;
}
.actions {
  display: flex;
  justify-content: flex-end;
  gap: 10px;
  margin-top: 12px;
}
.alert {
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 12px;
}
.error { border: 1px solid #f0b8b3; color: var(--danger); background: #fff5f5; }
.notice { border: 1px solid #b7dfc8; color: var(--ok); background: #f1fbf5; }
@media (max-width: 720px) {
  .topbar {
    grid-template-columns: 1fr;
    gap: 10px;
    padding: 12px 16px;
  }
  .nav { flex-wrap: wrap; }
  .shell { padding: 16px; }
}
```

- [ ] **Step 8: Run focused tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py -v
uv run ruff check .
uv run mypy
```

Expected: tests, ruff, and mypy pass.

- [ ] **Step 9: Commit**

Run:

```bash
git add src/mm_post_bot/web tests/test_web_app.py
git commit -m "feat: add web app authentication foundation"
```

Expected: commit succeeds.

## Task 5: Composer And Draft Routes

**Files:**

- Modify: `src/mm_post_bot/web/routes.py`
- Modify: `src/mm_post_bot/web/templates/composer.html`
- Create: `src/mm_post_bot/web/templates/drafts.html`
- Create: `src/mm_post_bot/web/templates/draft_detail.html`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Add failing composer and draft route tests**

Append to `tests/test_web_app.py`:

```python
def _csrf_from(response_text: str) -> str:
    marker = 'name="csrf" value="'
    start = response_text.index(marker) + len(marker)
    end = response_text.index('"', start)
    return response_text[start:end]


def test_composer_saves_draft(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    csrf = _csrf_from(client.get("/").text)

    response = client.post(
        "/drafts",
        data={"csrf": csrf, "message": "Web draft"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/drafts"
    drafts = ctx.post_drafts.list_for_owner("alice-id")
    assert drafts[0].message == "Web draft"


def test_drafts_page_lists_saved_drafts(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Queued web post",
        message_sha256="hash",
    )

    response = client.get("/drafts")

    assert response.status_code == 200
    assert "Queued web post" in response.text
    assert "Open" in response.text


def test_draft_detail_updates_message(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Old web draft",
        message_sha256="old",
    )
    csrf = _csrf_from(client.get(f"/drafts/{draft.id}").text)

    response = client.post(
        f"/drafts/{draft.id}",
        data={"csrf": csrf, "message": "Updated web draft"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == f"/drafts/{draft.id}"
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).message == "Updated web draft"


def test_draft_delete_marks_draft_deleted(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Delete web draft",
        message_sha256="hash",
    )
    csrf = _csrf_from(client.get(f"/drafts/{draft.id}").text)

    response = client.post(
        f"/drafts/{draft.id}/delete",
        data={"csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/drafts"
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "deleted"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py::test_composer_saves_draft tests/test_web_app.py::test_drafts_page_lists_saved_drafts tests/test_web_app.py::test_draft_detail_updates_message tests/test_web_app.py::test_draft_delete_marks_draft_deleted -v
```

Expected: missing routes or 404 responses.

- [ ] **Step 3: Add request context helper for service calls**

In `src/mm_post_bot/web/routes.py`, import:

```python
from mm_post_bot.commands.context import CommandContext
from mm_post_bot.mm_client import MattermostClient
from mm_post_bot.repository import (
    AuditRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPostDefaultRepo,
    UserPreferenceRepo,
    UserRepo,
)
from mm_post_bot.services.posting import create_draft, update_draft_message
```

Add helper:

```python
def _command_context(request: Request) -> CommandContext:
    cfg = settings(request)
    session = current_session(request)
    conn = request.app.state.conn
    return CommandContext(
        caller_user_id=session.user_id,
        caller_username=session.username,
        channel_id="web",
        channel_type=None,
        user_repo=UserRepo(conn),
        user_preference_repo=UserPreferenceRepo(conn),
        user_bot_repo=UserBotRepo(conn),
        user_channel_repo=UserChannelRepo(conn),
        user_post_default_repo=UserPostDefaultRepo(conn),
        draft_capture_repo=DraftCaptureRepo(conn),
        post_draft_repo=PostDraftRepo(conn),
        audit_repo=AuditRepo(conn),
        manager_mm=MattermostClient(cfg.mm_rest_base, cfg.mm_bot_token, verify_ssl=cfg.mm_verify_ssl),
        manager_user_id="web",
        admin_usernames=frozenset(cfg.admin_usernames),
        mm_rest_base=cfg.mm_rest_base,
        mm_url=str(cfg.mm_url).rstrip("/"),
        token_encryption_key=cfg.token_encryption_key,
        mm_verify_ssl=cfg.mm_verify_ssl,
        default_locale=cfg.default_locale,
        locale=cfg.default_locale,
        web_login_token_repo=repos(request).web_login_tokens,
        web_base_url=str(cfg.web_base_url).rstrip("/"),
        web_login_token_ttl_seconds=cfg.web_login_token_ttl_seconds,
    )
```

- [ ] **Step 4: Add composer and draft routes**

In `src/mm_post_bot/web/routes.py`, add:

```python
from fastapi import Form
from fastapi.responses import RedirectResponse


@router.post("/drafts")
async def save_draft(request: Request, message: str = Form(...), csrf: str = Form(...)) -> Response:
    from .deps import require_csrf

    require_csrf(request, csrf)
    command_ctx = _command_context(request)
    create_draft(command_ctx, message)
    return RedirectResponse("/drafts", status_code=303)


@router.get("/drafts", response_class=HTMLResponse)
async def drafts_page(request: Request) -> HTMLResponse:
    session = current_session(request)
    repo_set = repos(request)
    drafts = repo_set.post_drafts.list_for_owner(session.user_id)
    return templates.TemplateResponse(
        request,
        "drafts.html",
        {
            "request": request,
            "title": "Drafts",
            "session": session,
            "csrf": csrf_token(request),
            "drafts": drafts,
        },
    )


@router.get("/drafts/{draft_id}", response_class=HTMLResponse)
async def draft_detail(request: Request, draft_id: int) -> HTMLResponse:
    session = current_session(request)
    repo_set = repos(request)
    draft = repo_set.post_drafts.get_for_owner(session.user_id, draft_id)
    return templates.TemplateResponse(
        request,
        "draft_detail.html",
        {
            "request": request,
            "title": f"Draft #{draft.id}",
            "session": session,
            "csrf": csrf_token(request),
            "draft": draft,
        },
    )


@router.post("/drafts/{draft_id}")
async def update_draft(
    request: Request,
    draft_id: int,
    message: str = Form(...),
    csrf: str = Form(...),
) -> Response:
    from .deps import require_csrf

    require_csrf(request, csrf)
    command_ctx = _command_context(request)
    update_draft_message(command_ctx, draft_id, message)
    return RedirectResponse(f"/drafts/{draft_id}", status_code=303)


@router.post("/drafts/{draft_id}/delete")
async def delete_draft(request: Request, draft_id: int, csrf: str = Form(...)) -> Response:
    from .deps import require_csrf

    require_csrf(request, csrf)
    session = current_session(request)
    repos(request).post_drafts.soft_delete(session.user_id, draft_id)
    return RedirectResponse("/drafts", status_code=303)
```

- [ ] **Step 5: Add draft templates**

Create `src/mm_post_bot/web/templates/drafts.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="workspace">
  <div class="toolbar">
    <h1>Drafts</h1>
    <a class="button secondary" href="/">New draft</a>
  </div>
  <table class="grid">
    <thead>
      <tr>
        <th>ID</th>
        <th>Preview</th>
        <th>Created</th>
        <th>Action</th>
      </tr>
    </thead>
    <tbody>
      {% for draft in drafts %}
      <tr>
        <td>#{{ draft.id }}</td>
        <td>{{ draft.message.splitlines()[0] }}</td>
        <td>{{ draft.created_at }}</td>
        <td><a class="button secondary" href="/drafts/{{ draft.id }}">Open</a></td>
      </tr>
      {% else %}
      <tr><td colspan="4" class="empty">No saved drafts.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

Create `src/mm_post_bot/web/templates/draft_detail.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="workspace">
  <div class="toolbar">
    <h1>Draft #{{ draft.id }}</h1>
    <a class="button secondary" href="/drafts">Back</a>
  </div>
  <form method="post" action="/drafts/{{ draft.id }}" class="composer-form">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label for="message">Post body</label>
    <textarea id="message" name="message" rows="14">{{ draft.message }}</textarea>
    <div class="actions">
      <button type="submit">Save changes</button>
    </div>
  </form>
  <form method="post" action="/drafts/{{ draft.id }}/delete" class="danger-form">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <button type="submit" class="danger">Delete draft</button>
  </form>
</section>
{% endblock %}
```

Append to `src/mm_post_bot/web/static/app.css`:

```css
.grid {
  width: 100%;
  border-collapse: collapse;
}
.grid th, .grid td {
  border-bottom: 1px solid var(--line);
  padding: 10px;
  text-align: left;
  vertical-align: top;
}
.grid th {
  color: var(--muted);
  font-size: 12px;
  text-transform: uppercase;
}
.empty { color: var(--muted); }
.danger-form { margin-top: 16px; }
button.danger {
  background: var(--danger);
  border-color: var(--danger);
}
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py -v
uv run ruff check .
uv run mypy
```

Expected: web app tests, ruff, and mypy pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/mm_post_bot/web tests/test_web_app.py
git commit -m "feat: add web composer and drafts"
```

Expected: commit succeeds.

## Task 6: Targets Routes

**Files:**

- Modify: `src/mm_post_bot/web/routes.py`
- Create: `src/mm_post_bot/web/templates/targets.html`
- Modify: `src/mm_post_bot/web/static/app.css`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Add failing target route tests**

Append to `tests/test_web_app.py`:

```python
def test_targets_page_lists_aliases_and_default(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher",
        token_fingerprint="fp",
    )
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    ctx.user_post_defaults.set_for_owner("alice-id", bot_alias="news", channel_alias="town")

    response = client.get("/targets")

    assert response.status_code == 200
    assert "news-bot" in response.text
    assert "town" in response.text
    assert "Default: news -> town" in response.text
    assert "@postbot !channel add-current &lt;alias&gt;" in response.text


def test_set_and_clear_default_from_targets(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.user_bots.add(
        owner_user_id="alice-id",
        alias="news",
        bot_user_id="bot-id",
        bot_username="news-bot",
        bot_display_name=None,
        token_ciphertext="cipher",
        token_fingerprint="fp",
    )
    ctx.user_channels.add(owner_user_id="alice-id", alias="town", channel_id="channel-id")
    csrf = _csrf_from(client.get("/targets").text)

    response = client.post(
        "/targets/default",
        data={"csrf": csrf, "bot_alias": "news", "channel_alias": "town"},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert ctx.user_post_defaults.get_for_owner("alice-id").bot.alias == "news"

    csrf = _csrf_from(client.get("/targets").text)
    response = client.post(
        "/targets/default/clear",
        data={"csrf": csrf},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert ctx.user_post_defaults.get_for_owner("alice-id") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py::test_targets_page_lists_aliases_and_default tests/test_web_app.py::test_set_and_clear_default_from_targets -v
```

Expected: 404 for `/targets`.

- [ ] **Step 3: Add target routes**

In `src/mm_post_bot/web/routes.py`, add:

```python
@router.get("/targets", response_class=HTMLResponse)
async def targets_page(request: Request) -> HTMLResponse:
    session = current_session(request)
    repo_set = repos(request)
    default = repo_set.user_post_defaults.get_for_owner(session.user_id)
    stale_default = default is None and repo_set.user_post_defaults.has_for_owner(session.user_id)
    return templates.TemplateResponse(
        request,
        "targets.html",
        {
            "request": request,
            "title": "Targets",
            "session": session,
            "csrf": csrf_token(request),
            "bots": repo_set.user_bots.list_for_owner(session.user_id),
            "channels": repo_set.user_channels.list_for_owner(session.user_id),
            "default": default,
            "stale_default": stale_default,
            "error": "",
        },
    )


@router.post("/targets/default")
async def set_default_target(
    request: Request,
    bot_alias: str = Form(...),
    channel_alias: str = Form(...),
    csrf: str = Form(...),
) -> Response:
    from .deps import require_csrf

    require_csrf(request, csrf)
    session = current_session(request)
    repos(request).user_post_defaults.set_for_owner(
        session.user_id,
        bot_alias=bot_alias,
        channel_alias=channel_alias,
    )
    return RedirectResponse("/targets", status_code=303)


@router.post("/targets/default/clear")
async def clear_default_target(request: Request, csrf: str = Form(...)) -> Response:
    from .deps import require_csrf

    require_csrf(request, csrf)
    session = current_session(request)
    repos(request).user_post_defaults.clear_for_owner(session.user_id)
    return RedirectResponse("/targets", status_code=303)
```

- [ ] **Step 4: Add targets template**

Create `src/mm_post_bot/web/templates/targets.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="workspace">
  <div class="toolbar">
    <h1>Targets</h1>
    <a class="button secondary" href="/">Composer</a>
  </div>
  {% if default %}
  <div class="status-line">Default: {{ default.bot.alias }} -> {{ default.channel.alias }}</div>
  {% elif stale_default %}
  <div class="alert error">Default target is incomplete because one alias was removed.</div>
  {% else %}
  <div class="status-line muted">No default target configured.</div>
  {% endif %}

  <div class="columns">
    <section>
      <h2>Posting bots</h2>
      <table class="grid">
        <thead><tr><th>Alias</th><th>Username</th></tr></thead>
        <tbody>
          {% for bot in bots %}
          <tr><td>{{ bot.alias }}</td><td>{{ bot.bot_username }}</td></tr>
          {% else %}
          <tr><td colspan="2" class="empty">No posting bots.</td></tr>
          {% endfor %}
        </tbody>
      </table>
    </section>

    <section>
      <h2>Channels</h2>
      <table class="grid">
        <thead><tr><th>Alias</th><th>Channel ID</th></tr></thead>
        <tbody>
          {% for channel in channels %}
          <tr><td>{{ channel.alias }}</td><td>{{ channel.channel_id }}</td></tr>
          {% else %}
          <tr><td colspan="2" class="empty">No channels.</td></tr>
          {% endfor %}
        </tbody>
      </table>
      <p class="hint">Use @postbot !channel add-current &lt;alias&gt; in Mattermost to bind the current channel without copying an ID.</p>
    </section>
  </div>

  <form method="post" action="/targets/default" class="target-form">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label for="bot_alias">Bot alias</label>
    <select id="bot_alias" name="bot_alias">
      {% for bot in bots %}<option value="{{ bot.alias }}">{{ bot.alias }}</option>{% endfor %}
    </select>
    <label for="channel_alias">Channel alias</label>
    <select id="channel_alias" name="channel_alias">
      {% for channel in channels %}<option value="{{ channel.alias }}">{{ channel.alias }}</option>{% endfor %}
    </select>
    <div class="actions">
      <button type="submit">Set default</button>
    </div>
  </form>
  <form method="post" action="/targets/default/clear" class="danger-form">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <button type="submit" class="danger">Clear default</button>
  </form>
</section>
{% endblock %}
```

Append to `src/mm_post_bot/web/static/app.css`:

```css
.columns {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 20px;
}
h2 {
  font-size: 16px;
  margin: 18px 0 10px;
}
.status-line {
  border: 1px solid var(--line);
  border-radius: 6px;
  padding: 10px 12px;
  margin-bottom: 16px;
}
.muted, .hint { color: var(--muted); }
.target-form {
  display: grid;
  grid-template-columns: 1fr 1fr auto;
  align-items: end;
  gap: 12px;
  margin-top: 20px;
}
@media (max-width: 720px) {
  .columns, .target-form { grid-template-columns: 1fr; }
}
```

- [ ] **Step 5: Run focused tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py -v
uv run ruff check .
uv run mypy
```

Expected: web app tests, ruff, and mypy pass.

- [ ] **Step 6: Commit**

Run:

```bash
git add src/mm_post_bot/web tests/test_web_app.py
git commit -m "feat: add web target management"
```

Expected: commit succeeds.

## Task 7: Web Publish And Audit

**Files:**

- Modify: `src/mm_post_bot/web/routes.py`
- Modify: `src/mm_post_bot/web/templates/draft_detail.html`
- Create: `src/mm_post_bot/web/templates/audit.html`
- Modify: `tests/test_web_app.py`

- [ ] **Step 1: Add failing publish and audit tests**

Append to `tests/test_web_app.py`:

```python
def _ready_target(ctx):
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


def test_publish_draft_from_web(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    _ready_target(ctx)
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Publish from web",
        message_sha256=hash_message("Publish from web"),
    )
    csrf = _csrf_from(client.get(f"/drafts/{draft.id}").text)

    response = client.post(
        f"/drafts/{draft.id}/publish",
        data={"csrf": csrf, "bot_alias": "", "channel_alias": ""},
        follow_redirects=False,
    )

    assert response.status_code == 303
    assert response.headers["location"] == "/audit"
    assert ctx.post_drafts.get_for_owner("alice-id", draft.id).status == "sent"
    assert ctx.created_posts[0]["message"] == "Publish from web"


def test_audit_page_lists_records(ctx, web_settings):
    app = create_app(settings=web_settings, conn=ctx.conn)
    client = TestClient(app)
    _login(client, ctx)
    ctx.audits.record(
        caller_user_id="alice-id",
        caller_username="alice",
        draft_id=10,
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

    response = client.get("/audit")

    assert response.status_code == 200
    assert "news-bot" in response.text
    assert "post-id" in response.text
    assert "success" in response.text
```

Import `encrypt_token` and `hash_message` from `mm_post_bot.security`.

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py::test_publish_draft_from_web tests/test_web_app.py::test_audit_page_lists_records -v
```

Expected: publish route and audit route are missing.

- [ ] **Step 3: Add publish route**

In `src/mm_post_bot/web/routes.py`, import:

```python
from mm_post_bot.services.posting import (
    PublishDraftRequest,
    PublishError,
    TargetRequest,
    publish_draft,
)
```

Add:

```python
@router.post("/drafts/{draft_id}/publish")
async def publish_draft_route(
    request: Request,
    draft_id: int,
    bot_alias: str = Form(""),
    channel_alias: str = Form(""),
    csrf: str = Form(...),
) -> Response:
    from .deps import require_csrf

    require_csrf(request, csrf)
    command_ctx = _command_context(request)
    target = TargetRequest(
        bot_alias=bot_alias or None,
        channel_alias=channel_alias or None,
    )
    try:
        await publish_draft(
            command_ctx,
            PublishDraftRequest(draft_id=draft_id, target=target),
        )
    except PublishError as exc:
        raise HTTPException(status_code=400, detail=exc.code) from exc
    return RedirectResponse("/audit", status_code=303)
```

- [ ] **Step 4: Update draft detail template with publish controls**

Add below the save form in `src/mm_post_bot/web/templates/draft_detail.html`:

```html
  <form method="post" action="/drafts/{{ draft.id }}/publish" class="target-form">
    <input type="hidden" name="csrf" value="{{ csrf }}">
    <label for="bot_alias">Bot alias</label>
    <input id="bot_alias" name="bot_alias" placeholder="Use default">
    <label for="channel_alias">Channel alias</label>
    <input id="channel_alias" name="channel_alias" placeholder="Use default">
    <div class="actions">
      <button type="submit">Publish</button>
    </div>
  </form>
```

- [ ] **Step 5: Add audit route and template**

In `src/mm_post_bot/web/routes.py`, add:

```python
@router.get("/audit", response_class=HTMLResponse)
async def audit_page(request: Request) -> HTMLResponse:
    session = current_session(request)
    records = repos(request).audits.list_for_user(session.user_id, limit=50)
    return templates.TemplateResponse(
        request,
        "audit.html",
        {
            "request": request,
            "title": "Audit",
            "session": session,
            "csrf": csrf_token(request),
            "records": records,
        },
    )
```

Create `src/mm_post_bot/web/templates/audit.html`:

```html
{% extends "base.html" %}
{% block content %}
<section class="workspace">
  <div class="toolbar">
    <h1>Audit</h1>
    <a class="button secondary" href="/drafts">Drafts</a>
  </div>
  <table class="grid">
    <thead>
      <tr>
        <th>Created</th>
        <th>Status</th>
        <th>Draft</th>
        <th>Bot</th>
        <th>Channel</th>
        <th>Post</th>
        <th>Error</th>
      </tr>
    </thead>
    <tbody>
      {% for record in records %}
      <tr>
        <td>{{ record.created_at }}</td>
        <td>{{ record.status }}</td>
        <td>{% if record.draft_id %}#{{ record.draft_id }}{% endif %}</td>
        <td>{{ record.bot_username or "" }}</td>
        <td>{{ record.channel_link }}{% if record.resolved_channel_id %} ({{ record.resolved_channel_id }}){% endif %}</td>
        <td>{{ record.mattermost_post_id or "" }}</td>
        <td>{{ record.error_code or "" }} {{ record.error_message or "" }}</td>
      </tr>
      {% else %}
      <tr><td colspan="7" class="empty">No audit records.</td></tr>
      {% endfor %}
    </tbody>
  </table>
</section>
{% endblock %}
```

- [ ] **Step 6: Run focused tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_web_app.py -v
uv run ruff check .
uv run mypy
```

Expected: web app tests, ruff, and mypy pass.

- [ ] **Step 7: Commit**

Run:

```bash
git add src/mm_post_bot/web tests/test_web_app.py
git commit -m "feat: add web publish and audit views"
```

Expected: commit succeeds.

## Task 8: Runtime, Documentation, And Visual Verification

**Files:**

- Modify: `.env.example`
- Modify: `docker-compose.yml`
- Modify: `Dockerfile`
- Modify: `README.md`

- [ ] **Step 1: Add web env vars**

Modify `.env.example`:

```dotenv
WEB_BASE_URL=http://localhost:8080
WEB_SESSION_SECRET=replace-with-at-least-32-random-characters
WEB_COOKIE_SECURE=false
WEB_HOST=0.0.0.0
WEB_PORT=8080
WEB_LOGIN_TOKEN_TTL_SECONDS=300
WEB_SESSION_MAX_AGE_SECONDS=604800
```

- [ ] **Step 2: Add compose web service**

Modify `docker-compose.yml`:

```yaml
  mm-post-bot-web:
    build: .
    command: ["mm-post-bot-web"]
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "${WEB_PORT:-8080}:${WEB_PORT:-8080}"
    environment:
      MM_URL: ${MM_URL}
      MM_BOT_TOKEN: ${MM_BOT_TOKEN}
      MM_ADMINS: ${MM_ADMINS}
      MM_VERIFY_SSL: ${MM_VERIFY_SSL:-true}
      DB_URL: postgresql://${POSTGRES_USER:-mm_post}:${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required}@postgres/${POSTGRES_DB:-mm_post_bot}
      TOKEN_ENCRYPTION_KEY: ${TOKEN_ENCRYPTION_KEY}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      DEFAULT_LOCALE: ${DEFAULT_LOCALE:-en}
      WEB_BASE_URL: ${WEB_BASE_URL:-http://localhost:8080}
      WEB_SESSION_SECRET: ${WEB_SESSION_SECRET:?WEB_SESSION_SECRET is required}
      WEB_COOKIE_SECURE: ${WEB_COOKIE_SECURE:-false}
      WEB_HOST: ${WEB_HOST:-0.0.0.0}
      WEB_PORT: ${WEB_PORT:-8080}
      WEB_LOGIN_TOKEN_TTL_SECONDS: ${WEB_LOGIN_TOKEN_TTL_SECONDS:-300}
      WEB_SESSION_MAX_AGE_SECONDS: ${WEB_SESSION_MAX_AGE_SECONDS:-604800}
```

Also add the same `WEB_*` environment variables to the existing `mm-post-bot` service except `WEB_HOST` and `WEB_PORT`, because the bot needs `WEB_BASE_URL`, `WEB_SESSION_SECRET`, and login TTL to create links.

- [ ] **Step 3: Keep Dockerfile compatible with both scripts**

No command change is required in `Dockerfile`; keep:

```dockerfile
CMD ["python", "-m", "mm_post_bot"]
```

The compose web service overrides `command` with `mm-post-bot-web`.

- [ ] **Step 4: Document web UI**

In `README.md`, add `!web` to commands and add a section:

```markdown
## Web UI

The web UI is a private companion workspace for approved users. It is not a public landing page.

Start both bot and web services:

```bash
docker compose up -d --build
```

An approved user opens Mattermost DM with the manager bot and runs:

```text
!web
```

The bot replies with a one-time login link. After login, the user can:

- compose and save drafts;
- edit unsent drafts;
- publish drafts through the same sending path as `!send`;
- inspect posting bots, channel aliases, and the default target;
- set or clear the default target;
- review audit records.

Channel alias creation still supports the Mattermost-first shortcut:

```text
@postbot !channel add-current <alias>
```

Dynamic channel lookup and scheduled posting are outside this web UI phase.
```

Add config rows to the environment table:

```markdown
| `WEB_BASE_URL` | web | Public base URL used in `!web` login links. |
| `WEB_SESSION_SECRET` | web | At least 32 random characters for signed sessions and CSRF tokens. |
| `WEB_COOKIE_SECURE` | web | Set `true` behind HTTPS. |
| `WEB_HOST` | web | Web bind host, default `0.0.0.0`. |
| `WEB_PORT` | web | Web bind/published port, default `8080`. |
| `WEB_LOGIN_TOKEN_TTL_SECONDS` | web | One-time login link lifetime, default `300`. |
| `WEB_SESSION_MAX_AGE_SECONDS` | web | Session cookie lifetime, default `604800`. |
```

- [ ] **Step 5: Run full automated verification**

Run:

```bash
uv run pytest -p no:cacheprovider
uv run ruff check .
uv run mypy
git diff --check
```

Expected:

- pytest reports all tests passed;
- ruff reports no issues;
- mypy reports success;
- `git diff --check` prints no whitespace errors.

- [ ] **Step 6: Run local web server for browser verification**

Run:

```bash
WEB_BASE_URL=http://localhost:8080 WEB_SESSION_SECRET=12345678901234567890123456789012 uv run mm-post-bot-web
```

Expected: Uvicorn starts and listens on `http://0.0.0.0:8080`.

Open `http://localhost:8080/login-required` in the in-app browser.

Verify:

- page is not blank;
- header and login-required message are visible;
- no text overlaps at desktop width;
- resize to mobile width and confirm navigation/header text wraps cleanly.

Stop the server after browser verification.

- [ ] **Step 7: Commit**

Run:

```bash
git add .env.example docker-compose.yml Dockerfile README.md
git commit -m "docs: document posting web UI runtime"
```

Expected: commit succeeds.

## Final Verification

Run from the Phase 2 worktree:

```bash
uv run pytest -p no:cacheprovider
uv run ruff check .
uv run mypy
git diff --check
```

Expected:

- pytest reports all tests passed;
- ruff reports no issues;
- mypy reports success;
- `git diff --check` prints no output.

If implementation is complete and verification is green, use `superpowers:requesting-code-review` for a review subagent. Address findings with `superpowers:receiving-code-review`, rerun the full verification, then use `superpowers:finishing-a-development-branch`.

## Self-Review

Spec coverage:

- `!web` one-time DM login: Task 2.
- Short-lived single-use token storage: Task 1 and Task 2.
- Signed HTTP-only sessions and CSRF: Task 4.
- Composer: Task 5.
- Draft queue and draft detail: Task 5.
- Target dashboard with default readiness and add-current hint: Task 6.
- Publishing through the same path as `!send`: Task 3 and Task 7.
- Audit view: Task 7.
- Separate web process and compose service: Task 4 and Task 8.
- Documentation and runtime verification: Task 8.

Placeholder scan:

- No prohibited placeholder tokens are used.
- Each code-changing step names exact files and includes concrete code or concrete command lines.

Type consistency:

- `CommandContext` receives `WebLoginTokenRepo`, `web_base_url`, and `web_login_token_ttl_seconds` before `!web` and web routes use them.
- `PostDraftRepo.update_message` and `AuditRepo.list_for_user(limit=...)` are defined before routes call them.
- `PublishDraftRequest`, `TargetRequest`, `PublishError`, and `publish_draft` are defined before `send.py` and web publish routes import them.
