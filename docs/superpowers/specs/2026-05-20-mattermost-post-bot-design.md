# Mattermost Post Bot MVP Design

## Summary

Build a Python service for a self-hosted Mattermost Team Edition 10.11 server that lets approved Mattermost users publish messages to channels from bot accounts they personally added to the service.

The MVP uses PostgreSQL 15 for state, listens to Mattermost messages through a single manager bot account, and publishes posts through user-provided bot tokens. The service does not use a system admin personal access token and does not create or manage Mattermost bot accounts.

## Reference Project

The implementation should follow the structure of the `mm-bot-manager` reference project where it fits:

- Python package under `src/`.
- `uv` project management.
- `httpx` for Mattermost REST API calls.
- `websockets` for the Mattermost WebSocket event stream.
- `pydantic-settings` for configuration.
- `structlog` for structured logging.
- Command dispatcher with individual command modules.
- Repository layer over SQLite/PostgreSQL-style SQL.
- Docker Compose with PostgreSQL 15.
- Unit tests with `pytest`, `respx`, and PostgreSQL integration tests where useful.

The reference manages bot account creation and token minting. This project differs deliberately: users bring existing bot tokens, and the post bot stores those tokens encrypted so it can publish messages later.

## Non-Goals

- No `MM_TOKEN` or system admin personal access token.
- No creation, deletion, disabling, or editing of Mattermost bot accounts.
- No token minting or token revocation through Mattermost admin APIs.
- No web UI in the MVP.
- No scheduled posts, media uploads, previews, draft editing, or approvals for individual posts in the MVP.
- No free-form `team/channel-name` input in the first stage; users provide a Mattermost channel link.

## Configuration

Required environment variables:

- `MM_URL`: base Mattermost URL, for example `https://mm.internal`.
- `MM_BOT_TOKEN`: personal access token of the manager bot account. Used for WebSocket auth and replies.
- `MM_ADMINS`: comma-separated Mattermost usernames who administer this service.
- `DB_URL`: PostgreSQL DSN.
- `TOKEN_ENCRYPTION_KEY`: application secret used to encrypt stored user bot tokens.

Optional environment variables:

- `MM_VERIFY_SSL`: defaults to `true`; may be `false` for local/self-signed test servers.
- `LOG_LEVEL`: defaults to `INFO`.

`MM_TOKEN` is mentioned only as an explicitly excluded legacy/admin setting. It must not exist in the runtime configuration surface for this MVP.

## Roles and Users

The service has two roles:

- `admin`: a Mattermost user whose username is listed in `MM_ADMINS`.
- `user`: a registered and approved Mattermost user.

User statuses:

- `pending`: registration requested, awaiting admin approval.
- `approved`: allowed to use posting features.
- `blocked`: explicitly denied access until unblocked.

Admins are treated as approved users automatically. They can approve, block, unblock, and list users. They can also add their own bot tokens and post through their own bot list like any approved user.

## Registration Flow

1. A Mattermost user sends `!register` to the manager bot.
2. If the sender is configured as an admin, the service ensures an approved admin record exists and replies with the current status.
3. If the sender is unknown, the service creates a `pending` user record.
4. All admins receive a best-effort DM notification through the manager bot.
5. An admin approves or blocks the user with an admin command.
6. Blocked users cannot add bots, list bots, remove bots, or publish posts.

## Bot Token Flow

Users add existing bot tokens to their own list:

```text
!bot add <alias> <token>
```

Rules:

- `!bot add` is accepted only in a direct message with the manager bot.
- The service validates the provided token by calling `GET /api/v4/users/me` with that token.
- The returned user must be usable as a posting identity. If Mattermost exposes bot-account metadata in the response, the service should reject non-bot users. If the response does not expose a reliable bot flag, the MVP records the identity and relies on the token's Mattermost permissions.
- The token is encrypted before being stored.
- The plaintext token is never logged, echoed, or stored outside the encrypted column.
- The service stores a non-secret fingerprint for troubleshooting and duplicate detection.
- Alias uniqueness is scoped to the owner user.

Users can list and remove only their own added bots.

## Draft Preparation Flow

Users prepare a post in a direct message with the manager bot before choosing where to send it:

```text
!draft
```

The service:

1. Checks that the caller is approved and not blocked.
2. Starts a pending draft capture session for the caller.
3. Replies with instructions to send the post body as the next normal direct message.
4. Stores the next non-command direct message from that caller as a draft.
5. Replies with the draft id and the send command format.

Example:

```text
!draft
```

The manager bot replies:

```text
Send the post body as your next direct message. Use `!draft cancel` to cancel.
```

The user sends a normal message:

```text
Release notes

- Fixed channel sync
- Added audit log
```

The manager bot stores the text and replies:

```text
Draft #42 saved. Send it with:
!send 42 --bot <alias> --channel <mattermost-channel-link>
```

Draft capture rules:

- Draft capture is accepted only in a direct message with the manager bot.
- Only non-command messages are captured as draft bodies. Messages beginning with `!` are processed as commands and do not become draft bodies.
- A user may have at most one active draft capture session.
- `!draft cancel` cancels the active capture session.
- Pending draft capture expires after 30 minutes.
- A saved draft belongs only to the user who created it.

## Send Flow

Users publish a saved draft with:

```text
!send <draft_id> --bot <alias> --channel <mattermost-channel-link>
```

The service:

1. Checks that the caller is approved and not blocked.
2. Loads the caller's draft by id and checks that it is still in `draft` status.
3. Loads the caller's bot by alias.
4. Decrypts the bot token in memory.
5. Parses the Mattermost channel link.
6. Resolves the channel using the selected bot token.
7. Posts the draft body using `POST /api/v4/posts` with the selected bot token.
8. Marks the draft as `sent`.
9. Records a post audit entry with caller, draft, bot, target channel, status, and Mattermost post id when available.
10. Replies to the caller through the manager bot.

In the first stage, channel input must be a Mattermost channel link such as:

```text
https://mm.internal/team-name/channels/channel-name
```

The parser should accept the configured `MM_URL` host and extract `team-name` and `channel-name`. Channel resolution should happen through the selected bot token so Mattermost permissions remain the source of truth.

## Commands

User commands:

- `!help`: show available commands for the caller's role and status.
- `!register`: request or refresh registration.
- `!status`: show registration status.
- `!bot add <alias> <token>`: add a bot token to the caller's bot list; DM only.
- `!bot list`: list the caller's active bots without showing token values.
- `!bot remove <alias>`: remove a bot from the caller's list.
- `!draft`: start capturing the next normal DM as a draft body.
- `!draft cancel`: cancel active draft capture.
- `!draft list`: list the caller's saved drafts.
- `!draft show <draft_id>`: show a saved draft body.
- `!draft delete <draft_id>`: soft-delete a saved draft.
- `!send <draft_id> --bot <alias> --channel <link>`: publish a saved draft to a channel from the selected bot.

Admin commands:

- `!user approve <username-or-user-id>`: approve a pending or known user.
- `!user block <username-or-user-id>`: block a user.
- `!user unblock <username-or-user-id>`: restore an approved user.
- `!user list [pending|approved|blocked]`: list users by status.

All commands continue to use the command parsing style from the reference project: shell-like parsing via `shlex`, command handlers in separate modules, and a registry-based dispatcher.

## Data Model

Tables:

### `app_user`

- `user_id`: Mattermost user id, primary key.
- `username`: last known Mattermost username.
- `role`: `admin` or `user`.
- `status`: `pending`, `approved`, or `blocked`.
- `created_at`.
- `updated_at`.
- `approved_at`.
- `approved_by`.
- `blocked_at`.
- `blocked_by`.

### `user_bot`

- `id`: generated primary key.
- `owner_user_id`: references `app_user.user_id`.
- `alias`: user-scoped bot alias.
- `bot_user_id`: Mattermost user id returned by `/users/me` for the token.
- `bot_username`.
- `bot_display_name`.
- `token_ciphertext`: encrypted token value.
- `token_fingerprint`: non-secret fingerprint for diagnostics.
- `created_at`.
- `updated_at`.
- `deleted_at`: soft delete marker.

Uniqueness:

- `(owner_user_id, alias)` must be unique for non-deleted records.

### `draft_capture`

- `owner_user_id`: Mattermost user id, primary key.
- `created_at`.
- `expires_at`.

This table tracks users who ran `!draft` and are expected to send a normal DM containing the post body.

### `post_draft`

- `id`: generated primary key.
- `owner_user_id`: references `app_user.user_id`.
- `message`: draft body.
- `message_sha256`: hash of the message body.
- `status`: `draft`, `sent`, or `deleted`.
- `created_at`.
- `updated_at`.
- `sent_at`.
- `sent_by_user_bot_id`.
- `sent_channel_id`.
- `mattermost_post_id`.

Saved draft text is intentionally stored in the MVP so users can review drafts with `!draft show`. Deleted drafts are soft-deleted by setting `status = 'deleted'`.

### `post_audit_log`

- `id`: generated primary key.
- `caller_user_id`.
- `caller_username`.
- `draft_id`.
- `user_bot_id`.
- `bot_user_id`.
- `bot_username`.
- `channel_link`.
- `resolved_channel_id`.
- `resolved_team_name`.
- `resolved_channel_name`.
- `message_sha256`: hash of the message body, not the full message text.
- `status`: `success` or `failed`.
- `mattermost_post_id`.
- `error_code`.
- `error_message`.
- `created_at`.

The audit log should avoid storing full message bodies in the MVP unless explicitly needed later.

## Mattermost Client

The service should keep two client usage modes:

- Manager client: constructed with `MM_BOT_TOKEN`; used for WebSocket auth, command replies, and admin/user DMs.
- Dynamic posting client: constructed per operation with an encrypted user bot token after decryption; used for token validation, channel resolution, and posting.

Needed Mattermost API operations:

- `GET /users/me`: validate manager token at startup and validate user-provided bot tokens.
- `POST /channels/direct`: send DMs through the manager bot.
- `POST /posts`: send replies through the manager bot and publish through selected user bots.
- Channel resolution endpoints using the selected bot token. Prefer resolving from `team-name` and `channel-name` extracted from a channel link, so permissions are checked against the selected posting bot.

## Security Requirements

- Never log plaintext tokens.
- Never echo plaintext tokens back to users.
- Reject `!bot add` outside direct messages.
- Reject `!draft` capture outside direct messages.
- Redact command text in logs for commands that may contain secrets.
- Encrypt bot tokens at rest using `TOKEN_ENCRYPTION_KEY`.
- Keep decrypted tokens only in memory for a single operation.
- Do not include a system-admin Mattermost token setting in settings, `.env.example`, Docker Compose, or runtime code.
- Do not require Mattermost system admin privileges for normal operation.
- Treat Mattermost permissions as authoritative: if the selected bot token cannot see or post to the target channel, the post fails.

## Error Handling

User-facing errors should be specific but not leak secrets:

- Unregistered user: ask them to run `!register`.
- Pending user: explain that admin approval is required.
- Blocked user: explain that access is blocked.
- Unknown bot alias: ask them to use `!bot list`.
- No active draft capture: explain that the user should run `!draft`.
- Unknown draft id: ask them to use `!draft list`.
- Already sent or deleted draft: explain that the draft cannot be sent.
- Invalid bot token: say validation failed, without echoing the token.
- Invalid channel link: show the expected link form.
- Channel not visible to selected bot: explain that the bot may not be a member of the channel or lacks access.
- Post failure: report the Mattermost error category where safe, and store a redacted audit entry.

Operational errors should be logged with structured context and redaction.

## Testing Strategy

Unit tests:

- Command parsing and dispatch.
- Registration and admin command authorization.
- User status gates for bot, draft, and send commands.
- Bot alias uniqueness and soft deletion.
- Token validation and encryption boundaries.
- Draft capture, cancellation, expiry, listing, showing, deletion, and ownership isolation.
- Channel link parsing.
- Send command success and failure paths.
- Redaction behavior for secret-bearing commands.

HTTP tests:

- Mattermost client operations with `respx`.
- Token validation through `/users/me`.
- Channel resolution through selected bot token.
- Posting through selected bot token.

Database tests:

- Repository tests using SQLite-compatible behavior if retained for local tests.
- PostgreSQL 15 integration tests for schema, indexes, constraints, and transactions.

Manual MVP test against `https://mm.internal/i`:

1. Configure `MM_URL`, `MM_BOT_TOKEN`, `MM_ADMINS`, `DB_URL`, and `TOKEN_ENCRYPTION_KEY`.
2. Start PostgreSQL 15 and the bot service.
3. Send `!register` from a non-admin user.
4. Approve the user from an admin account.
5. Add an existing bot token in a DM.
6. Send `!draft` in a DM, then send the post body as a normal DM.
7. Send the saved draft to a channel by passing a Mattermost channel link.
8. Confirm the message appears from the selected bot account.
9. Block the user and confirm posting is denied.

## Future Extensions

The data model should leave room for:

- Scheduled posts.
- Draft editing.
- Message previews.
- Attachments and file uploads.
- Per-channel permissions inside the service.
- Shared bot catalogs.
- Post templates.
- Approval workflows for specific posts.
- Web UI for composing and scheduling posts.

These are explicitly out of scope for the MVP implementation.
