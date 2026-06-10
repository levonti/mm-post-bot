# Default Post Targets Design

## Summary

Add per-user default post targets so an approved user can publish a saved draft with the short command:

```text
!send <draft_id>
```

The default target is a pair of the user's existing posting bot and channel alias. "Default bot" means a user-added posting bot from `user_bot`, not the manager bot configured by `MM_BOT_TOKEN`.

The current explicit send flow remains supported:

```text
!send <draft_id> --bot <bot_alias> --channel <channel_alias>
```

Explicit flags override stored defaults, so users can keep a normal happy path while still choosing another bot or channel for one-off sends.

## Goals

- Reduce the common send path after draft capture from a long command to `!send <draft_id>`.
- Let users view their current default bot and channel.
- Let users set, update, and clear defaults.
- Reuse existing `user_bot` and `user_channel` records instead of duplicating tokens or channel IDs.
- Preserve current access checks, audit behavior, localization, and explicit send syntax.

## Non-Goals

- No global defaults shared by all users.
- No automatic creation of bots or channel aliases.
- No sending through the manager bot account.
- No implicit defaults based on the first bot/channel unless the user explicitly sets them.
- No new approval flow or per-channel permission layer inside this service.

## Command Surface

Add a new user command namespace:

```text
!default
!default set --bot <bot_alias> --channel <channel_alias>
!default clear
```

Rules:

- Commands require an approved user, like `!bot`, `!channel`, `!draft`, and `!send`.
- Commands are DM-only because they expose a user's personal bot/channel setup.
- `!default` shows the configured default pair or says that no defaults are configured.
- `!default set` validates that both aliases belong to the caller and are active before saving.
- `!default clear` removes the caller's default pair.
- `!help` includes the new commands for approved users.
- `!draft` save replies should mention both options: the short `!send <draft_id>` form and the explicit form for users who have not set defaults yet.

## Send Behavior

`!send` accepts these forms:

```text
!send <draft_id>
!send <draft_id> --bot <bot_alias>
!send <draft_id> --channel <channel_alias>
!send <draft_id> --bot <bot_alias> --channel <channel_alias>
```

Resolution order:

1. Parse and validate the draft id.
2. Load the caller's stored default pair when either `--bot` or `--channel` is missing.
3. Use explicit flag values for any provided flag.
4. Reject the command with a clear usage/defaults error if a required bot or channel is still missing.
5. Continue through the existing locked send path: load draft, load bot, load channel, decrypt token, post to Mattermost, mark draft sent, and record audit.

Examples:

- If defaults are `news` and `town`, `!send 42` behaves like `!send 42 --bot news --channel town`.
- If defaults are `news` and `town`, `!send 42 --channel urgent` sends with bot `news` to channel `urgent`.
- If no defaults exist, `!send 42` replies with instructions to run `!default set --bot <alias> --channel <alias>` or use the explicit send form.

## Data Model

Add a dedicated table:

```sql
CREATE TABLE IF NOT EXISTS user_post_default (
    owner_user_id           TEXT PRIMARY KEY REFERENCES app_user(user_id),
    default_user_bot_id     BIGINT NOT NULL REFERENCES user_bot(id),
    default_user_channel_id BIGINT NOT NULL REFERENCES user_channel(id),
    created_at              TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at              TIMESTAMPTZ NOT NULL DEFAULT now()
);
```

The table stores foreign keys to existing user-owned alias records. It does not store bot tokens, bot aliases, channel aliases, or channel IDs directly.

Repository behavior:

- `get_for_owner(owner_user_id)` returns the default pair, including current bot and channel records.
- `set_for_owner(owner_user_id, bot_alias, channel_alias)` resolves active aliases owned by that same user and upserts their IDs.
- `clear_for_owner(owner_user_id)` deletes the default row.
- `get_for_owner` joins bot and channel records through the same owner and treats owner mismatches or soft-deleted rows as invalid for sending and display.

This avoids a second source of truth. If a channel alias is updated with `!channel set`, the default still points to the same `user_channel` row and therefore uses the updated channel ID.

## Stale Defaults

Defaults can become stale when a user removes a bot or channel alias. The service should not silently send through a deleted target.

Behavior:

- `!default` reports that the stored default is incomplete or stale and asks the user to set it again.
- `!send <draft_id>` without enough explicit flags returns a defaults error if it would need a stale target.
- `!send <draft_id> --bot valid --channel valid` still works even if the stored defaults are stale, because both required values are explicit.
- Removing a bot or channel does not need to clear the default row immediately; soft-delete plus validation is enough and preserves simple command boundaries.

## Audit And Security

Successful and failed sends continue to use the existing `post_audit_log` behavior.

- `channel_link` continues to store the requested channel alias for compatibility with the current audit schema.
- `resolved_channel_id` stores the resolved Mattermost channel ID.
- The selected posting bot is recorded through the existing bot audit fields.
- Default resolution must not log, echo, or expose bot token material.
- Unknown or stale defaults should produce safe user-facing errors and should not attempt a Mattermost API call.

## Error Handling And Localization

Add localized messages for:

- default command usage;
- no defaults configured;
- defaults set;
- defaults cleared;
- bot alias not found while setting defaults;
- channel alias not found while setting defaults;
- stale default bot/channel;
- `!send` missing bot/channel because no default is available.

English and Russian catalogs must both be updated.

## Implementation Shape

Add:

- `UserPostDefault` dataclass and `UserPostDefaultRepo` in `repository.py`;
- `user_post_default` schema in `db.py`;
- `user_post_default_repo` on `CommandContext` and `CommandContextFactory`;
- `src/mm_post_bot/commands/defaults.py`;
- routes for `("default",)`, `("default", "set")`, and `("default", "clear")`;
- send argument resolution that accepts partial flags and fills missing aliases from defaults.

Keep the actual Mattermost publish logic in `send.py` rather than introducing a second sender path.

## Testing

Repository tests:

- set, get, update, and clear defaults;
- owner scoping;
- channel alias updates are reflected through the stored channel row;
- soft-deleted bot/channel defaults are treated as stale.

Command tests:

- `!default` shows empty state;
- `!default set --bot news --channel town` saves and displays current defaults;
- `!default clear` removes defaults;
- setting defaults rejects unknown bot or channel aliases;
- default commands require approved users and DMs;
- localized Russian replies work.

Send tests:

- `!send <draft_id>` publishes through stored defaults;
- `!send <draft_id> --bot other` uses explicit bot and default channel;
- `!send <draft_id> --channel urgent` uses default bot and explicit channel;
- `!send <draft_id>` fails safely when no defaults exist;
- stale defaults fail safely without creating a Mattermost post;
- fully explicit `!send` still works when defaults are absent or stale;
- audit fields match the effective bot/channel used.

Documentation tests or assertions should update help text and draft-save response expectations.

## Compatibility

Existing users can keep using the explicit send command with no behavior change. Existing database rows remain valid because the new table is additive. Users opt into shorter sends by running `!default set --bot <alias> --channel <alias>`.
