# Channel Aliases Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add per-user Mattermost channel aliases backed by channel IDs and use those aliases for draft publishing.

**Architecture:** Store user-owned channel aliases in PostgreSQL using the same soft-delete and owner-scoped uniqueness pattern as `user_bot`. Add `!channel` commands for CRUD, pass a `UserChannelRepo` through `CommandContext`, and change `!send` to resolve `--channel <alias>` to a stored `channel_id` before calling `create_post`.

**Tech Stack:** Python 3.14, psycopg 3, PostgreSQL 15, pytest/testcontainers, Mattermost REST API.

---

### Task 1: Repository And Schema

**Files:**
- Modify: `src/mm_post_bot/db.py`
- Modify: `src/mm_post_bot/repository.py`
- Test: `tests/test_repository_postgres.py`

- [ ] Write failing repository tests for adding, listing, updating, deleting, and owner-scoped alias reuse.
- [ ] Run `uv run pytest tests/test_repository_postgres.py -q` and confirm failures mention missing `UserChannelRepo` or table.
- [ ] Add `user_channel` table, `UserChannel` dataclass, row mapper, and `UserChannelRepo`.
- [ ] Run `uv run pytest tests/test_repository_postgres.py -q` and confirm repository tests pass.

### Task 2: Command Surface

**Files:**
- Create: `src/mm_post_bot/commands/channel.py`
- Modify: `src/mm_post_bot/commands/context.py`
- Modify: `src/mm_post_bot/commands/__init__.py`
- Modify: `src/mm_post_bot/dispatcher.py`
- Test: `tests/test_commands.py`

- [ ] Write failing command tests for `!channel add`, `!channel set`, `!channel remove`, `!channel list`, and `!channel show`.
- [ ] Run `uv run pytest tests/test_commands.py -q` and confirm failures for missing commands/context repo.
- [ ] Add `UserChannelRepo` to `CommandContext` and `CommandContextFactory`.
- [ ] Implement `channel.py` command handlers and registry routes.
- [ ] Run `uv run pytest tests/test_commands.py -q` and confirm channel command tests pass.

### Task 3: Send By Alias

**Files:**
- Modify: `src/mm_post_bot/commands/send.py`
- Modify: `tests/test_commands.py`
- Modify: `tests/test_dispatcher.py`
- Test: `tests/test_commands.py`

- [ ] Write failing tests showing `!send <draft_id> --bot <alias> --channel <channel_alias>` posts directly to stored `channel_id`.
- [ ] Write failing tests showing old Mattermost channel links are rejected by usage or alias lookup.
- [ ] Remove link parsing and channel-name resolution from `send.py`.
- [ ] Record audits with the requested channel alias and resolved channel ID.
- [ ] Run `uv run pytest tests/test_commands.py tests/test_dispatcher.py -q` and confirm green.

### Task 4: Help And Documentation

**Files:**
- Modify: `src/mm_post_bot/commands/help.py`
- Modify: `src/mm_post_bot/dispatcher.py`
- Modify: `README.md`
- Test: `tests/test_commands.py`
- Test: `tests/test_dispatcher.py`

- [ ] Update `!help` to include channel alias commands and the new `!send` syntax.
- [ ] Update draft-save reply to show `--channel <channel_alias>`.
- [ ] Update README examples and remove channel-link MVP language.
- [ ] Run `uv run pytest tests/test_commands.py tests/test_dispatcher.py -q`.

### Task 5: Final Verification And Delivery

**Files:**
- Review all modified files.

- [ ] Run `uv run ruff check src tests`.
- [ ] Run `uv run ruff format --check src tests`.
- [ ] Run `uv run mypy`.
- [ ] Run `uv run pytest -q`.
- [ ] Commit implementation and push `ai/mattermost-post-bot-mvp`.
- [ ] Rebuild the local container with `docker compose up -d --build` and confirm startup logs show `runtime_started` and `mattermost_ws_connected`.
