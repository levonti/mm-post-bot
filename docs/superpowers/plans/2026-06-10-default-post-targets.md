# Default Post Targets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let approved users configure a default posting bot/channel pair and publish drafts with `!send <draft_id>`.

**Architecture:** Store the default target in a new per-user `user_post_default` table that references existing `user_bot` and `user_channel` rows. Add a `UserPostDefaultRepo`, pass it through `CommandContext`, implement `!default` commands, and update `!send` to fill missing `--bot` and `--channel` values from the stored default while preserving the explicit send path.

**Tech Stack:** Python 3.14, PostgreSQL 15, psycopg 3, pytest/testcontainers, ruff, mypy.

---

## File Structure

- Modify `src/mm_post_bot/db.py`: add the `user_post_default` table.
- Modify `src/mm_post_bot/repository.py`: add `UserPostDefault`, row mapping, and `UserPostDefaultRepo`.
- Modify `src/mm_post_bot/commands/context.py`: add `user_post_default_repo` to `CommandContext`.
- Modify `src/mm_post_bot/dispatcher.py`: construct `UserPostDefaultRepo` in `CommandContextFactory`.
- Create `src/mm_post_bot/commands/defaults.py`: implement `!default`, `!default set`, and `!default clear`.
- Modify `src/mm_post_bot/commands/__init__.py`: register default command routes.
- Modify `src/mm_post_bot/commands/send.py`: allow missing bot/channel flags and resolve them from defaults.
- Modify `src/mm_post_bot/i18n.py`: add default and send messages in English and Russian, plus help text.
- Modify `src/mm_post_bot/commands/help.py`: include default commands in approved-user help.
- Modify `tests/test_repository_postgres.py`: cover default repository behavior.
- Modify `tests/test_commands.py`: cover `!default`, default sends, overrides, stale defaults, help, and localization.
- Modify `tests/test_dispatcher.py`: update draft-save response expectations and test contexts.
- Modify `README.md`: document the new command flow.

---

### Task 1: Default Repository And Schema

**Files:**
- Modify: `src/mm_post_bot/db.py`
- Modify: `src/mm_post_bot/repository.py`
- Test: `tests/test_repository_postgres.py`

- [ ] **Step 1: Write failing repository tests**

Add `UserPostDefaultRepo` to the import list in `tests/test_repository_postgres.py`:

```python
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
```

Change the `repos` fixture to yield the default repo between channels and captures:

```python
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
```

Update existing tuple unpacking in repository tests:

```python
users, bots, channels, _, *_ = repos
users, _, channels, _, *_ = repos
users, _, _, _, captures, drafts, _ = repos
```

Add these helper functions near the fixture:

```python
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
```

Add these tests after the channel alias tests:

```python
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


def test_user_post_default_tracks_channel_alias_updates(repos):
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
```

- [ ] **Step 2: Run repository tests and verify failure**

Run:

```bash
uv run pytest tests/test_repository_postgres.py -q
```

Expected: failure during import with `ImportError` for `UserPostDefaultRepo`.

- [ ] **Step 3: Add schema**

In `src/mm_post_bot/db.py`, insert this table after `user_channel` indexes and before `draft_capture`:

```sql
CREATE TABLE IF NOT EXISTS user_post_default (
    owner_user_id           TEXT PRIMARY KEY REFERENCES app_user(user_id),
    default_user_bot_id     BIGINT NOT NULL REFERENCES user_bot(id),
    default_user_channel_id BIGINT NOT NULL REFERENCES user_channel(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_user_post_default_bot
    ON user_post_default(default_user_bot_id);
CREATE INDEX IF NOT EXISTS idx_user_post_default_channel
    ON user_post_default(default_user_channel_id);
```

- [ ] **Step 4: Add repository dataclass and mapper**

In `src/mm_post_bot/repository.py`, add this dataclass after `UserChannel`:

```python
@dataclass(frozen=True, slots=True)
class UserPostDefault:
    owner_user_id: str
    bot: UserBot
    channel: UserChannel
    created_at: datetime
    updated_at: datetime
```

Add this mapper after `_user_channel_from_row`:

```python
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
```

- [ ] **Step 5: Add repository class**

In `src/mm_post_bot/repository.py`, add this class after `UserChannelRepo`:

```python
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
        bot = UserBotRepo(self._conn).get_by_owner_and_alias(owner_user_id, bot_alias)
        channel = UserChannelRepo(self._conn).get_by_owner_and_alias(owner_user_id, channel_alias)
        now = _now()
        self._conn.execute(
            """
            INSERT INTO user_post_default (
                owner_user_id,
                default_user_bot_id,
                default_user_channel_id,
                updated_at
            )
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (owner_user_id) DO UPDATE SET
                default_user_bot_id = EXCLUDED.default_user_bot_id,
                default_user_channel_id = EXCLUDED.default_user_channel_id,
                updated_at = EXCLUDED.updated_at
            """,
            (owner_user_id, bot.id, channel.id, now),
        )
        current = self.get_for_owner(owner_user_id)
        if current is None:
            raise LookupError(f"user_post_default not found after set: {owner_user_id}")
        return current

    def clear_for_owner(self, owner_user_id: str) -> None:
        self._conn.execute(
            "DELETE FROM user_post_default WHERE owner_user_id = %s",
            (owner_user_id,),
        )
```

- [ ] **Step 6: Run repository tests and verify pass**

Run:

```bash
uv run pytest tests/test_repository_postgres.py -q
```

Expected: all repository tests pass.

- [ ] **Step 7: Commit repository work**

```bash
git add src/mm_post_bot/db.py src/mm_post_bot/repository.py tests/test_repository_postgres.py
git commit -m "feat: add user post defaults repository"
```

---

### Task 2: Context Wiring

**Files:**
- Modify: `src/mm_post_bot/commands/context.py`
- Modify: `src/mm_post_bot/dispatcher.py`
- Modify: `tests/test_commands.py`
- Modify: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing context tests**

In `tests/test_commands.py`, add `UserPostDefaultRepo` to the repository import list and to `CommandFixture`:

```python
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
```

```python
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
```

In `CommandFixture.make`, pass the repo:

```python
user_post_default_repo=self.user_post_defaults,
```

In the `ctx` fixture, construct it:

```python
user_post_defaults=UserPostDefaultRepo(pg_conn),
```

In `tests/test_dispatcher.py`, update `_draft_body_ctx` to pass the default repo dependency:

```python
user_post_default_repo=cast(Any, object()),
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
uv run pytest tests/test_commands.py::test_send_posts_saved_draft tests/test_dispatcher.py::test_handle_draft_body_saves_active_capture -q
```

Expected: failure because `CommandContext` has no `user_post_default_repo` field.

- [ ] **Step 3: Add repo to CommandContext**

In `src/mm_post_bot/commands/context.py`, import `UserPostDefaultRepo`:

```python
from ..repository import (
    AuditRepo,
    DraftCaptureRepo,
    PostDraftRepo,
    UserBotRepo,
    UserChannelRepo,
    UserPostDefaultRepo,
    UserPreferenceRepo,
    UserRepo,
)
```

Add the dataclass field after `user_channel_repo`:

```python
user_post_default_repo: UserPostDefaultRepo
```

- [ ] **Step 4: Construct repo in context factory**

In `src/mm_post_bot/dispatcher.py`, import `UserPostDefaultRepo` and pass it after `user_channel_repo`:

```python
user_post_default_repo=UserPostDefaultRepo(self._conn),
```

- [ ] **Step 5: Run focused tests and verify pass**

Run:

```bash
uv run pytest tests/test_commands.py::test_send_posts_saved_draft tests/test_dispatcher.py::test_handle_draft_body_saves_active_capture -q
```

Expected: both tests pass.

- [ ] **Step 6: Commit context wiring**

```bash
git add src/mm_post_bot/commands/context.py src/mm_post_bot/dispatcher.py tests/test_commands.py tests/test_dispatcher.py
git commit -m "feat: wire post defaults into command context"
```

---

### Task 3: Default Command Surface

**Files:**
- Create: `src/mm_post_bot/commands/defaults.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/i18n.py`
- Modify: `src/mm_post_bot/commands/help.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing command tests**

Add these tests near the channel command tests in `tests/test_commands.py`:

```python
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
```

- [ ] **Step 2: Run command tests and verify failure**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: default command tests fail with `Unknown command: default`.

- [ ] **Step 3: Add i18n messages**

In `src/mm_post_bot/i18n.py`, add these English catalog entries near existing help and send keys:

```python
"help.defaults.title": "Defaults",
"help.defaults.show": "!default - show your default bot and channel",
"help.defaults.set": (
    "!default set --bot <alias> --channel <channel_alias> - set default target"
),
"help.defaults.clear": "!default clear - clear default target",
"default.usage": "Usage: !default [set --bot <alias> --channel <channel_alias>|clear]",
"default.set_usage": "Usage: !default set --bot <alias> --channel <channel_alias>",
"default.clear_usage": "Usage: !default clear",
"default.dm_only": "Please manage defaults in a direct message.",
"default.none": (
    "No default bot/channel configured. Set one with:\n"
    "!default set --bot <alias> --channel <channel_alias>"
),
"default.current": (
    "Default bot: {bot_alias} ({bot_username})\n"
    "Default channel: {channel_alias} ({channel_id})"
),
"default.set": "Default target set: bot {bot_alias}, channel {channel_alias}.",
"default.cleared": "Default target cleared.",
"default.bot_not_found": "Could not find a bot named {alias}.",
"default.channel_not_found": "Could not find a channel named {alias}.",
"default.stale": (
    "Default target is incomplete because its bot or channel was removed. Set it again with:\n"
    "!default set --bot <alias> --channel <channel_alias>"
),
```

Add these Russian entries:

```python
"help.defaults.title": "По умолчанию",
"help.defaults.show": "!default - показать bot и channel по умолчанию",
"help.defaults.set": (
    "!default set --bot <alias> --channel <channel_alias> - задать цель по умолчанию"
),
"help.defaults.clear": "!default clear - очистить цель по умолчанию",
"default.usage": (
    "Использование: !default [set --bot <alias> --channel <channel_alias>|clear]"
),
"default.set_usage": "Использование: !default set --bot <alias> --channel <channel_alias>",
"default.clear_usage": "Использование: !default clear",
"default.dm_only": "Управляйте настройками по умолчанию только в direct message.",
"default.none": (
    "Bot/channel по умолчанию не настроены. Задать можно командой:\n"
    "!default set --bot <alias> --channel <channel_alias>"
),
"default.current": (
    "Bot по умолчанию: {bot_alias} ({bot_username})\n"
    "Channel по умолчанию: {channel_alias} ({channel_id})"
),
"default.set": "Цель по умолчанию задана: bot {bot_alias}, channel {channel_alias}.",
"default.cleared": "Цель по умолчанию очищена.",
"default.bot_not_found": "Бот с именем {alias} не найден.",
"default.channel_not_found": "Channel alias {alias} не найден.",
"default.stale": (
    "Цель по умолчанию неполная: bot или channel был удалён. Задайте её заново:\n"
    "!default set --bot <alias> --channel <channel_alias>"
),
```

- [ ] **Step 4: Implement default command module**

Create `src/mm_post_bot/commands/defaults.py`:

```python
from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_default_command_access(ctx)
    if access_error is not None:
        return access_error

    if args.positional or args.flags:
        return ctx.t("default.usage")

    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    if default is None:
        if ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id):
            return ctx.t("default.stale")
        return ctx.t("default.none")

    return ctx.t(
        "default.current",
        bot_alias=default.bot.alias,
        bot_username=default.bot.bot_username,
        channel_alias=default.channel.alias,
        channel_id=default.channel.channel_id,
    )


async def set_defaults(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_default_command_access(ctx)
    if access_error is not None:
        return access_error

    parsed = _parse_set_args(args)
    if parsed is None:
        return ctx.t("default.set_usage")

    bot_alias, channel_alias = parsed
    try:
        ctx.user_bot_repo.get_by_owner_and_alias(ctx.caller_user_id, bot_alias)
    except LookupError:
        return ctx.t("default.bot_not_found", alias=bot_alias)

    try:
        ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, channel_alias)
    except LookupError:
        return ctx.t("default.channel_not_found", alias=channel_alias)

    default = ctx.user_post_default_repo.set_for_owner(
        ctx.caller_user_id,
        bot_alias=bot_alias,
        channel_alias=channel_alias,
    )
    return ctx.t(
        "default.set",
        bot_alias=default.bot.alias,
        channel_alias=default.channel.alias,
    )


async def clear(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_default_command_access(ctx)
    if access_error is not None:
        return access_error

    if args.positional or args.flags:
        return ctx.t("default.clear_usage")

    ctx.user_post_default_repo.clear_for_owner(ctx.caller_user_id)
    return ctx.t("default.cleared")


def _require_default_command_access(ctx: CommandContext) -> str | None:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error
    if ctx.channel_type != "D":
        return ctx.t("default.dm_only")
    return None


def _parse_set_args(args: ParsedArgs) -> tuple[str, str] | None:
    if args.positional or set(args.flags) != {"bot", "channel"}:
        return None

    bot_alias = args.flags["bot"]
    channel_alias = args.flags["channel"]
    if not isinstance(bot_alias, str) or not bot_alias:
        return None
    if not isinstance(channel_alias, str) or not channel_alias:
        return None
    return bot_alias, channel_alias
```

- [ ] **Step 5: Register default command routes**

In `src/mm_post_bot/commands/__init__.py`, update imports:

```python
from . import bot, channel, defaults, draft, lang, register, send, status, user_admin
```

Add routes before draft routes:

```python
("default",): defaults.show,
("default", "set"): defaults.set_defaults,
("default", "clear"): defaults.clear,
```

- [ ] **Step 6: Add help section**

In `src/mm_post_bot/commands/help.py`, add this section between Channels and Drafts in `_approved_user_sections`:

```python
_section(
    ctx.t("help.defaults.title"),
    [
        ctx.t("help.defaults.show"),
        ctx.t("help.defaults.set"),
        ctx.t("help.defaults.clear"),
    ],
),
```

- [ ] **Step 7: Run command tests and verify pass**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: all command tests pass.

- [ ] **Step 8: Commit default command work**

```bash
git add src/mm_post_bot/commands/defaults.py src/mm_post_bot/commands/__init__.py src/mm_post_bot/commands/help.py src/mm_post_bot/i18n.py tests/test_commands.py
git commit -m "feat: add default target commands"
```

---

### Task 4: Send With Defaults

**Files:**
- Modify: `src/mm_post_bot/commands/send.py`
- Modify: `src/mm_post_bot/i18n.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing send tests**

Add these tests near the existing send tests in `tests/test_commands.py`:

```python
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
```

- [ ] **Step 2: Run send tests and verify failure**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: failures showing `!send <draft_id>` and partial flag forms return usage.

- [ ] **Step 3: Add send i18n messages**

In `src/mm_post_bot/i18n.py`, change English usage and add defaults messages:

```python
"send.usage": "Usage: !send <draft_id> [--bot <alias>] [--channel <channel_alias>]",
"send.defaults_missing": (
    "No default bot/channel configured. Set one with:\n"
    "!default set --bot <alias> --channel <channel_alias>\n"
    "Or send explicitly with:\n"
    "!send <draft_id> --bot <alias> --channel <channel_alias>"
),
"send.default_stale": (
    "Default target is incomplete because its bot or channel was removed. Set it again with:\n"
    "!default set --bot <alias> --channel <channel_alias>"
),
```

Change Russian usage and add:

```python
"send.usage": "Использование: !send <draft_id> [--bot <alias>] [--channel <channel_alias>]",
"send.defaults_missing": (
    "Bot/channel по умолчанию не настроены. Задайте их командой:\n"
    "!default set --bot <alias> --channel <channel_alias>\n"
    "Или отправьте явно:\n"
    "!send <draft_id> --bot <alias> --channel <channel_alias>"
),
"send.default_stale": (
    "Цель по умолчанию неполная: bot или channel был удалён. Задайте её заново:\n"
    "!default set --bot <alias> --channel <channel_alias>"
),
```

- [ ] **Step 4: Update send parser and default resolution**

In `src/mm_post_bot/commands/send.py`, change the handle function to:

```python
async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    parsed = _parse_args(args)
    if parsed is None:
        return ctx.t("send.usage")

    draft_id, requested_bot_alias, requested_channel_alias = parsed
    resolved = _resolve_aliases(ctx, requested_bot_alias, requested_channel_alias)
    if isinstance(resolved, str):
        return resolved

    bot_alias, channel_alias = resolved
    async with _send_lock(ctx.caller_user_id, draft_id):
        return await _send_locked(ctx, draft_id, bot_alias, channel_alias)
```

Replace `_parse_args` with:

```python
def _parse_args(args: ParsedArgs) -> tuple[int, str | None, str | None] | None:
    if len(args.positional) != 1 or not set(args.flags).issubset({"bot", "channel"}):
        return None

    bot_alias = args.flags.get("bot")
    channel_alias = args.flags.get("channel")
    if bot_alias is not None and (not isinstance(bot_alias, str) or not bot_alias):
        return None
    if channel_alias is not None and (
        not isinstance(channel_alias, str) or not channel_alias
    ):
        return None

    try:
        draft_id = int(args.positional[0])
    except ValueError:
        return None
    if draft_id <= 0:
        return None

    return draft_id, bot_alias, channel_alias
```

Add this helper after `_parse_args`:

```python
def _resolve_aliases(
    ctx: CommandContext,
    bot_alias: str | None,
    channel_alias: str | None,
) -> tuple[str, str] | str:
    if bot_alias is not None and channel_alias is not None:
        return bot_alias, channel_alias

    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    if default is None:
        if ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id):
            return ctx.t("send.default_stale")
        return ctx.t("send.defaults_missing")

    return bot_alias or default.bot.alias, channel_alias or default.channel.alias
```

- [ ] **Step 5: Run send tests and verify pass**

Run:

```bash
uv run pytest tests/test_commands.py -q
```

Expected: all command tests pass.

- [ ] **Step 6: Commit send default behavior**

```bash
git add src/mm_post_bot/commands/send.py src/mm_post_bot/i18n.py tests/test_commands.py
git commit -m "feat: send drafts with default targets"
```

---

### Task 5: Help, Draft Reply, README, And Final Verification

**Files:**
- Modify: `src/mm_post_bot/i18n.py`
- Modify: `tests/test_dispatcher.py`
- Modify: `README.md`
- Test: `tests/test_commands.py`
- Test: `tests/test_dispatcher.py`

- [ ] **Step 1: Write failing documentation/help assertions**

In `tests/test_dispatcher.py`, update `test_handle_draft_body_saves_active_capture` assertions to expect both send forms:

```python
assert "!send 42" in response
assert "!send 42 --bot <alias> --channel <channel_alias>" in response
```

In `test_handle_draft_body_uses_selected_locale`, keep the existing Russian prefix assertion and add:

```python
assert "!send 42" in response
assert "!send 42 --bot <alias> --channel <channel_alias>" in response
```

In `tests/test_commands.py`, add:

```python
async def test_help_includes_default_commands_for_approved_user(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")

    reply = await dispatch(ctx.make("alice-id", "alice"), "!help")

    assert reply is not None
    assert "!default" in reply
    assert "!default set --bot <alias> --channel <channel_alias>" in reply
    assert "!default clear" in reply
```

- [ ] **Step 2: Run focused tests and verify failure**

Run:

```bash
uv run pytest tests/test_commands.py::test_help_includes_default_commands_for_approved_user tests/test_dispatcher.py::test_handle_draft_body_saves_active_capture tests/test_dispatcher.py::test_handle_draft_body_uses_selected_locale -q
```

Expected: dispatcher assertions fail until draft-save copy is updated.

- [ ] **Step 3: Update draft-save replies**

In `src/mm_post_bot/i18n.py`, change English `draft.saved` to:

```python
"draft.saved": (
    "Draft #{draft_id} saved. Send it with:\n"
    "!send {draft_id}\n"
    "Or choose target explicitly:\n"
    "!send {draft_id} --bot <alias> --channel <channel_alias>"
),
```

Change Russian `draft.saved` to:

```python
"draft.saved": (
    "Черновик #{draft_id} сохранён. Отправить его можно командой:\n"
    "!send {draft_id}\n"
    "Или выбрать цель явно:\n"
    "!send {draft_id} --bot <alias> --channel <channel_alias>"
),
```

- [ ] **Step 4: Update README command list and flow**

In `README.md`, add the default commands after channel commands:

```text
!default
!default set --bot <alias> --channel <channel_alias>
!default clear
```

Change the send command line to:

```text
!send <draft_id> [--bot <alias>] [--channel <channel_alias>]
```

In "Как работает draft-first flow", replace step 4 with:

```markdown
4. Если defaults настроены, опубликуйте его через `!send <draft_id>`.
   Для разового выбора цели используйте
   `!send <draft_id> --bot <alias> --channel <channel_alias>`.
```

In the smoke test, after adding bot and channel, add:

```text
!default set --bot news --channel town
```

Change the final smoke command to:

```text
!send 1
```

- [ ] **Step 5: Run focused tests and verify pass**

Run:

```bash
uv run pytest tests/test_commands.py::test_help_includes_default_commands_for_approved_user tests/test_dispatcher.py::test_handle_draft_body_saves_active_capture tests/test_dispatcher.py::test_handle_draft_body_uses_selected_locale -q
```

Expected: focused tests pass.

- [ ] **Step 6: Run final verification**

Run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
uv run pytest -q
```

Expected: all commands exit 0.

- [ ] **Step 7: Commit docs and final polish**

```bash
git add README.md src/mm_post_bot/i18n.py tests/test_commands.py tests/test_dispatcher.py
git commit -m "docs: document default target sends"
```

---

## Self-Review Notes

- Spec coverage: schema/repo is Task 1; command surface is Task 3; send behavior is Task 4; stale defaults, audit safety, and explicit override behavior are tested in Task 4; help, draft copy, README, localization, and final verification are Task 5.
- Placeholder scan: this plan contains no unresolved implementation steps.
- Type consistency: the plan uses `UserPostDefault`, `UserPostDefaultRepo`, `user_post_default_repo`, `get_for_owner`, `has_for_owner`, `set_for_owner`, and `clear_for_owner` consistently across tasks.
