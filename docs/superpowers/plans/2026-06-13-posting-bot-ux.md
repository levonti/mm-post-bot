# Posting Bot UX Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve the current Mattermost bot posting UX with setup guidance, current-channel aliasing, richer draft preview, and recovery-oriented replies.

**Architecture:** Add one small command helper module for target/status formatting, one new command module for `!setup` / `!next`, and focused changes to existing `channel`, `draft`, `send`, `help`, `dispatcher`, `i18n`, tests, and README. Keep all behavior inside the existing bot process and PostgreSQL schema.

**Tech Stack:** Python 3.14, existing command dispatcher, existing repository classes, PostgreSQL-backed tests with pytest/testcontainers, existing i18n catalog.

---

## Scope

This plan implements Phase 1 from `docs/superpowers/specs/2026-06-13-posting-ui-ux-design.md`.

Included:

- contextual state cards after draft save and draft show;
- `!setup` and `!next`;
- `@postbot !channel add-current <alias>`;
- recovery-oriented replies for missing/stale targets and unknown aliases;
- README/help updates for the new bot commands.

Excluded from this plan:

- web UI;
- Mattermost buttons/dialogs;
- scheduling;
- dynamic Mattermost channel lookup.

## File Structure

- Create `src/mm_post_bot/commands/posting_state.py`
  - Shared helper for draft previews, current default target state, setup state, and localized next-action text.
- Create `src/mm_post_bot/commands/setup.py`
  - Command handlers for `!setup` and `!next`.
- Modify `src/mm_post_bot/commands/__init__.py`
  - Register `setup` and `next`.
- Modify `src/mm_post_bot/commands/channel.py`
  - Add `add_current` handler that stores `ctx.channel_id` from a non-DM channel.
- Modify `src/mm_post_bot/commands/draft.py`
  - Use shared helper for richer `!draft show`.
- Modify `src/mm_post_bot/dispatcher.py`
  - Use shared helper for richer draft-save response.
- Modify `src/mm_post_bot/commands/send.py`
  - Add one-step recovery hints to safe send errors.
- Modify `src/mm_post_bot/commands/help.py`
  - Include `!setup`, `!next`, and `!channel add-current <alias>`.
- Modify `src/mm_post_bot/i18n.py`
  - Add English and Russian strings.
- Modify `tests/test_commands.py`
  - Add command-level coverage for setup, next, add-current, draft preview, and recovery copy.
- Modify `tests/test_dispatcher.py`
  - Update draft-save response tests.
- Modify `README.md`
  - Document the new commands and improved flow.

## Task 1: Shared Posting State Helper

**Files:**

- Create: `src/mm_post_bot/commands/posting_state.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing command-level tests for target-aware draft previews**

Append these tests near the existing draft tests in `tests/test_commands.py`:

```python
async def test_draft_show_includes_ready_target_context(ctx: CommandFixture):
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
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Release notes\nSecond line",
        message_sha256=hash_message("Release notes\nSecond line"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!draft show {draft.id}")

    assert reply is not None
    assert f"Draft #{draft.id}" in reply
    assert "Release notes\nSecond line" in reply
    assert "Target: bot news (news-bot), channel town (channel-id)" in reply
    assert f"Publish: !send {draft.id}" in reply
    assert f"Delete: !draft delete {draft.id}" in reply


async def test_draft_show_includes_missing_target_recovery(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Body without defaults",
        message_sha256=hash_message("Body without defaults"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!draft show {draft.id}")

    assert reply is not None
    assert "Target: no default bot/channel configured" in reply
    assert "!default set --bot <alias> --channel <channel_alias>" in reply
    assert f"!send {draft.id} --bot <alias> --channel <channel_alias>" in reply
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_draft_show_includes_ready_target_context tests/test_commands.py::test_draft_show_includes_missing_target_recovery -v
```

Expected: both tests fail because `!draft show` does not include target status or action hints yet.

- [ ] **Step 3: Add `posting_state.py`**

Create `src/mm_post_bot/commands/posting_state.py`:

```python
from dataclasses import dataclass
from typing import Literal

from .context import CommandContext

TargetStatus = Literal["ready", "missing", "stale"]


@dataclass(frozen=True, slots=True)
class TargetState:
    status: TargetStatus
    bot_alias: str | None = None
    bot_username: str | None = None
    channel_alias: str | None = None
    channel_id: str | None = None


def preview_line(message: str, *, max_length: int = 80) -> str:
    first_line = message.splitlines()[0].strip() if message.splitlines() else ""
    if len(first_line) <= max_length:
        return first_line
    return f"{first_line[: max_length - 3]}..."


def target_state(ctx: CommandContext) -> TargetState:
    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    if default is not None:
        return TargetState(
            status="ready",
            bot_alias=default.bot.alias,
            bot_username=default.bot.bot_username,
            channel_alias=default.channel.alias,
            channel_id=default.channel.channel_id,
        )
    if ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id):
        return TargetState(status="stale")
    return TargetState(status="missing")


def target_line(ctx: CommandContext, state: TargetState) -> str:
    if state.status == "ready":
        return ctx.t(
            "posting_state.target.ready",
            bot_alias=state.bot_alias,
            bot_username=state.bot_username,
            channel_alias=state.channel_alias,
            channel_id=state.channel_id,
        )
    if state.status == "stale":
        return ctx.t("posting_state.target.stale")
    return ctx.t("posting_state.target.missing")


def publish_hint(ctx: CommandContext, draft_id: int, state: TargetState) -> str:
    if state.status == "ready":
        return ctx.t("posting_state.publish.short", draft_id=draft_id)
    return ctx.t("posting_state.publish.explicit", draft_id=draft_id)


def default_recovery(ctx: CommandContext) -> str:
    return ctx.t("posting_state.default_recovery")
```

- [ ] **Step 4: Add i18n keys used by the helper**

In `src/mm_post_bot/i18n.py`, add these English keys near the other posting strings:

```python
"posting_state.target.ready": (
    "Target: bot {bot_alias} ({bot_username}), channel {channel_alias} ({channel_id})"
),
"posting_state.target.missing": "Target: no default bot/channel configured.",
"posting_state.target.stale": "Target: default bot/channel is incomplete because one was removed.",
"posting_state.publish.short": "Publish: !send {draft_id}",
"posting_state.publish.explicit": (
    "Publish: !send {draft_id} --bot <alias> --channel <channel_alias>"
),
"posting_state.default_recovery": (
    "Set a default with: !default set --bot <alias> --channel <channel_alias>"
),
```

Add these Russian keys in the `ru` catalog:

```python
"posting_state.target.ready": (
    "Цель: bot {bot_alias} ({bot_username}), channel {channel_alias} ({channel_id})"
),
"posting_state.target.missing": "Цель: bot/channel по умолчанию не настроены.",
"posting_state.target.stale": "Цель: bot/channel по умолчанию неполная, потому что один alias удалён.",
"posting_state.publish.short": "Опубликовать: !send {draft_id}",
"posting_state.publish.explicit": (
    "Опубликовать: !send {draft_id} --bot <alias> --channel <channel_alias>"
),
"posting_state.default_recovery": (
    "Задать цель по умолчанию: !default set --bot <alias> --channel <channel_alias>"
),
```

- [ ] **Step 5: Update `draft.show` to use the helper**

In `src/mm_post_bot/commands/draft.py`, import the helper:

```python
from .posting_state import default_recovery, publish_hint, target_line, target_state
```

Replace the final return in `show`:

```python
    state = target_state(ctx)
    lines = [
        ctx.t("draft.show", draft_id=draft.id, message=draft.message),
        target_line(ctx, state),
    ]
    if state.status != "ready":
        lines.append(default_recovery(ctx))
    lines.extend(
        [
            publish_hint(ctx, draft.id, state),
            ctx.t("posting_state.delete_hint", draft_id=draft.id),
        ]
    )
    return "\n".join(lines)
```

Add these i18n keys:

```python
"posting_state.delete_hint": "Delete: !draft delete {draft_id}",
```

```python
"posting_state.delete_hint": "Удалить: !draft delete {draft_id}",
```

- [ ] **Step 6: Run the focused tests to verify they pass**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_draft_show_includes_ready_target_context tests/test_commands.py::test_draft_show_includes_missing_target_recovery -v
```

Expected: both tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/mm_post_bot/commands/posting_state.py src/mm_post_bot/commands/draft.py src/mm_post_bot/i18n.py tests/test_commands.py
git commit -m "feat: add posting state helpers"
```

## Task 2: Current Channel Alias Command

**Files:**

- Modify: `src/mm_post_bot/commands/channel.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/commands/help.py`
- Modify: `src/mm_post_bot/i18n.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing tests for `!channel add-current`**

Append near the existing channel tests:

```python
async def test_channel_add_current_saves_current_channel_id(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    channel_ctx = ctx.make("alice-id", "alice", channel_type="O")
    channel_ctx = replace(channel_ctx, channel_id="current-channel-id")

    reply = await dispatch(channel_ctx, "!channel add-current town")

    assert reply is not None
    assert "added" in reply.lower()
    saved = ctx.user_channels.get_by_owner_and_alias("alice-id", "town")
    assert saved.channel_id == "current-channel-id"


async def test_channel_add_current_rejects_dm_duplicate_and_unapproved_user(ctx: CommandFixture):
    pending = await dispatch(ctx.make("alice-id", "alice", channel_type="O"), "!channel add-current town")
    assert pending is not None
    assert "register" in pending.lower()

    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    dm_reply = await dispatch(ctx.make("alice-id", "alice"), "!channel add-current town")
    assert dm_reply is not None
    assert "channel" in dm_reply.lower()

    channel_ctx = replace(ctx.make("alice-id", "alice", channel_type="O"), channel_id="current-channel-id")
    await dispatch(channel_ctx, "!channel add-current town")
    duplicate = await dispatch(channel_ctx, "!channel add-current town")
    assert duplicate is not None
    assert "already" in duplicate.lower()
```

- [ ] **Step 2: Run the tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_channel_add_current_saves_current_channel_id tests/test_commands.py::test_channel_add_current_rejects_dm_duplicate_and_unapproved_user -v
```

Expected: both tests fail because the route is not registered.

- [ ] **Step 3: Implement `add_current`**

In `src/mm_post_bot/commands/channel.py`, add:

```python
async def add_current(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    if ctx.channel_type == "D":
        return ctx.t("channel.add_current_channel_only")

    if len(args.positional) != 1:
        return ctx.t("channel.add_current_usage")

    alias = args.positional[0]
    try:
        ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        pass
    else:
        return ctx.t("channel.duplicate", alias=alias)

    channel = ctx.user_channel_repo.add(
        owner_user_id=ctx.caller_user_id,
        alias=alias,
        channel_id=ctx.channel_id,
    )
    return ctx.t("channel.add_current_added", alias=channel.alias)
```

- [ ] **Step 4: Register route and help text**

In `src/mm_post_bot/commands/__init__.py`, add:

```python
("channel", "add-current"): channel.add_current,
```

In `src/mm_post_bot/commands/help.py`, add `ctx.t("help.channels.add_current")` to the channel section.

In `src/mm_post_bot/i18n.py`, add English:

```python
"help.channels.add_current": (
    "@postbot !channel add-current <alias> - save the current channel as an alias"
),
"channel.add_current_usage": "Usage: !channel add-current <alias>",
"channel.add_current_channel_only": (
    "Run this from the Mattermost channel you want to save, for example: "
    "@postbot !channel add-current town"
),
"channel.add_current_added": "Added current channel as {alias}.",
```

Add Russian:

```python
"help.channels.add_current": (
    "@postbot !channel add-current <alias> - сохранить текущий канал как alias"
),
"channel.add_current_usage": "Использование: !channel add-current <alias>",
"channel.add_current_channel_only": (
    "Выполните эту команду в нужном Mattermost-канале, например: "
    "@postbot !channel add-current town"
),
"channel.add_current_added": "Текущий канал сохранён как {alias}.",
```

- [ ] **Step 5: Run focused channel tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_channel_add_current_saves_current_channel_id tests/test_commands.py::test_channel_add_current_rejects_dm_duplicate_and_unapproved_user tests/test_commands.py::test_help_changes_after_user_approval -v
```

Expected: all selected tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/mm_post_bot/commands/channel.py src/mm_post_bot/commands/__init__.py src/mm_post_bot/commands/help.py src/mm_post_bot/i18n.py tests/test_commands.py
git commit -m "feat: add current channel alias command"
```

## Task 3: Setup And Next Commands

**Files:**

- Create: `src/mm_post_bot/commands/setup.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/commands/help.py`
- Modify: `src/mm_post_bot/i18n.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing tests for `!setup` and `!next`**

Append near the help/status tests:

```python
async def test_setup_guides_unregistered_user(ctx: CommandFixture):
    reply = await dispatch(ctx.make("alice-id", "alice"), "!setup")

    assert reply is not None
    assert "Registration: not registered" in reply
    assert "Next: !register" in reply


async def test_setup_guides_partially_configured_approved_user(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")

    setup_reply = await dispatch(ctx.make("alice-id", "alice"), "!setup")
    next_reply = await dispatch(ctx.make("alice-id", "alice"), "!next")

    assert setup_reply is not None
    assert "Posting bots: 1" in setup_reply
    assert "Channels: none" in setup_reply
    assert "Next: !channel add <alias> <channel_id>" in setup_reply
    assert next_reply is not None
    assert next_reply == "Next: !channel add <alias> <channel_id>"


async def test_setup_guides_fully_configured_user_to_draft(ctx: CommandFixture):
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

    reply = await dispatch(ctx.make("alice-id", "alice"), "!setup")

    assert reply is not None
    assert "Default: news -> town" in reply
    assert "Next: !draft" in reply
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_setup_guides_unregistered_user tests/test_commands.py::test_setup_guides_partially_configured_approved_user tests/test_commands.py::test_setup_guides_fully_configured_user_to_draft -v
```

Expected: tests fail with unknown command replies.

- [ ] **Step 3: Add setup state helpers to `posting_state.py`**

Append to `src/mm_post_bot/commands/posting_state.py`:

```python
def user_status(ctx: CommandContext) -> str | None:
    try:
        return ctx.user_repo.get(ctx.caller_user_id).status
    except LookupError:
        return None


def setup_next_command(ctx: CommandContext) -> str:
    status = user_status(ctx)
    if status is None:
        return "!register"
    if status == "pending":
        return "!status"
    if status == "blocked":
        return "!status"
    if status != "approved":
        return "!status"
    if not ctx.user_bot_repo.list_for_owner(ctx.caller_user_id):
        return "!bot add <alias> <token>"
    if not ctx.user_channel_repo.list_for_owner(ctx.caller_user_id):
        return "!channel add <alias> <channel_id>"
    state = target_state(ctx)
    if state.status != "ready":
        return "!default set --bot <alias> --channel <channel_alias>"
    if not ctx.post_draft_repo.list_for_owner(ctx.caller_user_id):
        return "!draft"
    return "!draft list"


def setup_lines(ctx: CommandContext) -> list[str]:
    status = user_status(ctx)
    bots = ctx.user_bot_repo.list_for_owner(ctx.caller_user_id) if status == "approved" else []
    channels = ctx.user_channel_repo.list_for_owner(ctx.caller_user_id) if status == "approved" else []
    state = target_state(ctx) if status == "approved" else TargetState(status="missing")
    drafts = ctx.post_draft_repo.list_for_owner(ctx.caller_user_id) if status == "approved" else []
    status_text = status if status is not None else "not registered"
    bot_text = str(len(bots)) if bots else "none"
    channel_text = str(len(channels)) if channels else "none"
    if state.status == "ready":
        default_text = f"{state.bot_alias} -> {state.channel_alias}"
    elif state.status == "stale":
        default_text = "stale"
    else:
        default_text = "none"
    draft_text = str(len(drafts)) if drafts else "none"
    return [
        ctx.t("setup.registration", status=status_text),
        ctx.t("setup.bots", count=bot_text),
        ctx.t("setup.channels", count=channel_text),
        ctx.t("setup.default", value=default_text),
        ctx.t("setup.drafts", count=draft_text),
        ctx.t("setup.next", command=setup_next_command(ctx)),
    ]
```

- [ ] **Step 4: Add `setup.py` command handlers**

Create `src/mm_post_bot/commands/setup.py`:

```python
from .context import CommandContext
from .parser import ParsedArgs
from .posting_state import setup_lines, setup_next_command


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    if args.positional or args.flags:
        return ctx.t("setup.usage")
    return "\n".join(setup_lines(ctx))


async def next_action(ctx: CommandContext, args: ParsedArgs) -> str:
    if args.positional or args.flags:
        return ctx.t("next.usage")
    return ctx.t("setup.next", command=setup_next_command(ctx))
```

- [ ] **Step 5: Register commands and i18n**

In `src/mm_post_bot/commands/__init__.py`, import `setup`:

```python
from . import bot, channel, defaults, draft, lang, register, send, setup, status, user_admin
```

Add registry entries:

```python
("setup",): setup.show,
("next",): setup.next_action,
```

In `src/mm_post_bot/commands/help.py`, add `ctx.t("help.core.setup")` and `ctx.t("help.core.next")` to the core rows.

In `src/mm_post_bot/i18n.py`, add English:

```python
"help.core.setup": "!setup - show posting setup checklist",
"help.core.next": "!next - show the next recommended posting step",
"setup.usage": "Usage: !setup",
"next.usage": "Usage: !next",
"setup.registration": "Registration: {status}",
"setup.bots": "Posting bots: {count}",
"setup.channels": "Channels: {count}",
"setup.default": "Default: {value}",
"setup.drafts": "Drafts: {count}",
"setup.next": "Next: {command}",
```

Add Russian:

```python
"help.core.setup": "!setup - показать checklist настройки постинга",
"help.core.next": "!next - показать следующий рекомендуемый шаг",
"setup.usage": "Использование: !setup",
"next.usage": "Использование: !next",
"setup.registration": "Регистрация: {status}",
"setup.bots": "Posting-боты: {count}",
"setup.channels": "Каналы: {count}",
"setup.default": "По умолчанию: {value}",
"setup.drafts": "Черновики: {count}",
"setup.next": "Дальше: {command}",
```

- [ ] **Step 6: Run focused setup tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_setup_guides_unregistered_user tests/test_commands.py::test_setup_guides_partially_configured_approved_user tests/test_commands.py::test_setup_guides_fully_configured_user_to_draft tests/test_commands.py::test_help_mentions_lang_command -v
```

Expected: selected tests pass.

- [ ] **Step 7: Commit**

```bash
git add src/mm_post_bot/commands/posting_state.py src/mm_post_bot/commands/setup.py src/mm_post_bot/commands/__init__.py src/mm_post_bot/commands/help.py src/mm_post_bot/i18n.py tests/test_commands.py
git commit -m "feat: add posting setup guidance commands"
```

## Task 4: Draft Save State Card

**Files:**

- Modify: `src/mm_post_bot/dispatcher.py`
- Modify: `src/mm_post_bot/i18n.py`
- Modify: `tests/test_dispatcher.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Add a default-target fake to dispatcher tests**

In `tests/test_dispatcher.py`, add this fake near `_PostDraftRepo`:

```python
class _UserPostDefaultRepo:
    def get_for_owner(self, owner_user_id: str):
        return None

    def has_for_owner(self, owner_user_id: str) -> bool:
        return False
```

In `_draft_body_ctx`, replace `user_post_default_repo=cast(Any, object())` with:

```python
user_post_default_repo=cast(Any, _UserPostDefaultRepo()),
```

- [ ] **Step 2: Update dispatcher tests for richer draft-save replies**

In `tests/test_dispatcher.py`, update `test_handle_draft_body_saves_active_capture` assertions:

```python
    assert "Draft #42 saved" in response
    assert "Preview: hello from the draft" in response
    assert "Target: no default bot/channel configured" in response
    assert "!default set --bot <alias> --channel <channel_alias>" in response
    assert "Publish: !send 42 --bot <alias> --channel <channel_alias>" in response
    assert "Review: !draft show 42" in response
```

Update `test_handle_draft_body_uses_selected_locale`:

```python
    assert response.startswith("Черновик #42 сохранён.")
    assert "Предпросмотр: текст черновика" in response
    assert "Опубликовать: !send 42 --bot <alias> --channel <channel_alias>" in response
    assert "Проверить: !draft show 42" in response
```

- [ ] **Step 3: Run dispatcher tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_dispatcher.py::test_handle_draft_body_saves_active_capture tests/test_dispatcher.py::test_handle_draft_body_uses_selected_locale -v
```

Expected: tests fail because the old reply lacks preview, target, recovery, and review lines.

- [ ] **Step 4: Add review hint i18n and helper usage**

In `src/mm_post_bot/i18n.py`, add English:

```python
"draft.saved_header": "Draft #{draft_id} saved.",
"posting_state.preview": "Preview: {preview}",
"posting_state.review_hint": "Review: !draft show {draft_id}",
```

Add Russian:

```python
"draft.saved_header": "Черновик #{draft_id} сохранён.",
"posting_state.preview": "Предпросмотр: {preview}",
"posting_state.review_hint": "Проверить: !draft show {draft_id}",
```

Keep the existing `draft.saved` keys until this task passes, then remove unused use from `handle_draft_body` only. Do not delete catalog keys in this task.

- [ ] **Step 5: Update `handle_draft_body`**

In `src/mm_post_bot/dispatcher.py`, add imports:

```python
from .commands.posting_state import (
    default_recovery,
    preview_line,
    publish_hint,
    target_line,
    target_state,
)
```

Replace the final return in `handle_draft_body`:

```python
    state = target_state(ctx)
    lines = [
        ctx.t("draft.saved_header", draft_id=draft.id),
        ctx.t("posting_state.preview", preview=preview_line(body)),
        target_line(ctx, state),
    ]
    if state.status != "ready":
        lines.append(default_recovery(ctx))
    lines.extend(
        [
            publish_hint(ctx, draft.id, state),
            ctx.t("posting_state.review_hint", draft_id=draft.id),
        ]
    )
    return "\n".join(lines)
```

- [ ] **Step 6: Run dispatcher tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_dispatcher.py::test_handle_draft_body_saves_active_capture tests/test_dispatcher.py::test_handle_draft_body_uses_selected_locale -v
```

Expected: selected tests pass.

- [ ] **Step 7: Add an integration-style ready-target draft-save test**

Append to `tests/test_commands.py` near draft tests:

```python
async def test_saved_draft_reply_uses_ready_default_target(ctx: CommandFixture):
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
    await dispatch(ctx.make("alice-id", "alice"), "!draft")

    from mm_post_bot.dispatcher import handle_draft_body

    reply = await handle_draft_body(ctx.make("alice-id", "alice"), "Ready default body")

    assert reply is not None
    assert "Target: bot news (news-bot), channel town (channel-id)" in reply
    assert "Publish: !send" in reply
    assert "--bot <alias>" not in reply
```

- [ ] **Step 8: Run the integration-style test**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_saved_draft_reply_uses_ready_default_target -v
```

Expected: test passes.

- [ ] **Step 9: Commit**

```bash
git add src/mm_post_bot/dispatcher.py src/mm_post_bot/i18n.py tests/test_dispatcher.py tests/test_commands.py
git commit -m "feat: add draft save state cards"
```

## Task 5: Recovery-Oriented Send And Default Replies

**Files:**

- Modify: `src/mm_post_bot/i18n.py`
- Test: `tests/test_commands.py`

- [ ] **Step 1: Write failing tests for recovery hints**

Add near send/default tests:

```python
async def test_send_missing_defaults_points_to_lists_and_default_setup(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="No default body",
        message_sha256=hash_message("No default body"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!send {draft.id}")

    assert reply is not None
    assert "!bot list" in reply
    assert "!channel list" in reply
    assert "!default set --bot <alias> --channel <channel_alias>" in reply


async def test_send_unknown_channel_points_to_channel_list_and_add_current(ctx: CommandFixture):
    ctx.users.upsert_seen_user(user_id="alice-id", username="alice", is_admin=False)
    ctx.users.approve("alice-id", approved_by="admin-id")
    ctx.token_identities["secret-token"] = {
        "id": "bot-id",
        "username": "news-bot",
        "is_bot": True,
    }
    await dispatch(ctx.make("alice-id", "alice"), "!bot add news secret-token")
    draft = ctx.post_drafts.create(
        owner_user_id="alice-id",
        message="Missing channel body",
        message_sha256=hash_message("Missing channel body"),
    )

    reply = await dispatch(ctx.make("alice-id", "alice"), f"!send {draft.id} --bot news --channel missing")

    assert reply is not None
    assert "!channel list" in reply
    assert "@postbot !channel add-current <alias>" in reply
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_send_missing_defaults_points_to_lists_and_default_setup tests/test_commands.py::test_send_unknown_channel_points_to_channel_list_and_add_current -v
```

Expected: tests fail because current errors do not include the new recovery commands.

- [ ] **Step 3: Add recovery strings**

In `src/mm_post_bot/i18n.py`, replace the English `send.defaults_missing`, `send.default_stale`, `send.bot_not_found`, `send.channel_not_found`, and `default.stale` values with:

```python
"send.defaults_missing": (
    "No default bot/channel configured.\n"
    "Check aliases: !bot list and !channel list\n"
    "Set a default: !default set --bot <alias> --channel <channel_alias>\n"
    "Or send explicitly: !send <draft_id> --bot <alias> --channel <channel_alias>"
),
"send.default_stale": (
    "Default target is incomplete because its bot or channel was removed.\n"
    "Check aliases: !bot list and !channel list\n"
    "Set it again: !default set --bot <alias> --channel <channel_alias>\n"
    "Or clear it: !default clear"
),
"send.bot_not_found": "Could not find that bot. Check aliases with: !bot list",
"send.channel_not_found": (
    "Could not find that channel alias.\n"
    "Check aliases: !channel list\n"
    "From a channel, save it with: @postbot !channel add-current <alias>"
),
"default.stale": (
    "Default target is incomplete because its bot or channel was removed.\n"
    "Check aliases: !bot list and !channel list\n"
    "Set it again: !default set --bot <alias> --channel <channel_alias>\n"
    "Or clear it: !default clear"
),
```

Replace the Russian values with:

```python
"send.defaults_missing": (
    "Bot/channel по умолчанию не настроены.\n"
    "Проверить aliases: !bot list и !channel list\n"
    "Задать цель: !default set --bot <alias> --channel <channel_alias>\n"
    "Или отправить явно: !send <draft_id> --bot <alias> --channel <channel_alias>"
),
"send.default_stale": (
    "Цель по умолчанию неполная: bot или channel был удалён.\n"
    "Проверить aliases: !bot list и !channel list\n"
    "Задать заново: !default set --bot <alias> --channel <channel_alias>\n"
    "Или очистить: !default clear"
),
"send.bot_not_found": "Указанный бот не найден. Проверить aliases: !bot list",
"send.channel_not_found": (
    "Указанный channel alias не найден.\n"
    "Проверить aliases: !channel list\n"
    "Из канала можно сохранить alias: @postbot !channel add-current <alias>"
),
"default.stale": (
    "Цель по умолчанию неполная: bot или channel был удалён.\n"
    "Проверить aliases: !bot list и !channel list\n"
    "Задать заново: !default set --bot <alias> --channel <channel_alias>\n"
    "Или очистить: !default clear"
),
```

- [ ] **Step 4: Run focused recovery tests**

Run:

```bash
uv run pytest -p no:cacheprovider tests/test_commands.py::test_send_missing_defaults_points_to_lists_and_default_setup tests/test_commands.py::test_send_unknown_channel_points_to_channel_list_and_add_current tests/test_commands.py::test_default_shows_stale_state -v
```

Expected: selected tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/mm_post_bot/i18n.py tests/test_commands.py
git commit -m "feat: improve posting recovery hints"
```

## Task 6: README And Full Verification

**Files:**

- Modify: `README.md`
- Test: full repository test suite

- [ ] **Step 1: Update README command list**

In the user commands block in `README.md`, add:

```text
!setup
!next
```

Add this line after `!channel add <alias> <channel_id>`:

```text
@postbot !channel add-current <alias>
```

- [ ] **Step 2: Update README draft-first flow**

Replace the current draft-first flow with:

````markdown
Как работает draft-first flow:

1. Проверьте готовность настройки через `!setup`; бот покажет следующий шаг.
2. В DM manager-боту отправьте `!draft`.
3. Следующее обычное DM-сообщение сохранится как черновик и покажет preview, target и команды.
4. Проверьте черновик через `!draft show <draft_id>`.
5. Если defaults настроены, опубликуйте его через `!send <draft_id>`.
   Для разового выбора цели используйте
   `!send <draft_id> --bot <alias> --channel <channel_alias>`.

Чтобы добавить канал без копирования Mattermost channel ID, выполните в нужном канале:

```text
@postbot !channel add-current <alias>
```
````

- [ ] **Step 3: Run docs smoke check**

Run:

```bash
rg -n "!setup|!next|add-current|draft-first" README.md docs/superpowers/specs/2026-06-13-posting-ui-ux-design.md
```

Expected: output includes README entries for `!setup`, `!next`, `add-current`, and the existing design spec references.

- [ ] **Step 4: Run full tests**

Run:

```bash
uv run pytest -p no:cacheprovider
```

Expected: `186` or more tests pass, with `0` failures.

- [ ] **Step 5: Run whitespace check**

Run:

```bash
git diff --check
```

Expected: no output and exit code `0`.

- [ ] **Step 6: Commit**

```bash
git add README.md
git commit -m "docs: document posting UX commands"
```

## Final Verification Checklist

- [ ] `uv run pytest -p no:cacheprovider` passes with `0` failures.
- [ ] `git diff --check` exits `0`.
- [ ] `!setup` and `!next` are present in help and README.
- [ ] `@postbot !channel add-current <alias>` works only outside DM.
- [ ] `!draft show <draft_id>` includes message, target readiness, publish command, and delete command.
- [ ] Draft-save replies include preview, target readiness, publish command, and review command.
- [ ] Missing/stale/unknown target errors include concrete recovery commands.
- [ ] English and Russian catalogs contain all new keys.
