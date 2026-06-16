# Posting UI/UX Improvements Design

## Summary

Improve posting usability in two layers:

1. Make the current Mattermost bot flow easier to discover, verify, and recover from errors.
2. Add a web UI companion for composing, reviewing, publishing, and auditing posts.

The bot remains the lowest-friction path for users already working in Mattermost. The web UI becomes
the safer workspace for users who prepare posts repeatedly, manage several target channels, or need a
scan-friendly draft queue.

The recommended delivery order is:

1. Conversational UX polish in the existing bot.
2. Web UI companion over the same repository and database.
3. Mattermost buttons/dialogs and scheduling after an HTTP surface exists.

## Research Basis

The design is grounded in these findings:

- Nielsen Norman Group usability heuristics emphasize visible system status, recognition over recall,
  error prevention, user control, and contextual help:
  <https://www.nngroup.com/articles/ten-usability-heuristics/>
- Nielsen Norman Group chatbot guidance recommends simple bot tasks, visible capability boundaries,
  free-text plus selectable actions, saved context between tasks, and escape hatches:
  <https://www.nngroup.com/articles/chatbots/>
- Mattermost supports interactive messages with buttons, menus, ephemeral feedback, custom action
  errors, and channel/user menus:
  <https://developers.mattermost.com/integrate/plugins/interactive-messages/>
- Mattermost supports interactive dialogs with text, textarea, select, bool, date, datetime, dynamic
  selects, validation errors, and multi-step dialogs:
  <https://developers.mattermost.com/integrate/plugins/interactive-dialogs/>
- Mattermost custom slash commands can return ephemeral responses and rich attachments:
  <https://developers.mattermost.com/integrate/slash-commands/custom/>

Current repository context:

- The product is a Mattermost posting manager bot with encrypted posting bot tokens.
- Users register, add posting bot aliases, add channel aliases, save drafts, and publish drafts.
- Per-user default targets already exist, so `!send <draft_id>` is now the short happy path.
- Bot responses are currently plain Mattermost posts created through `MattermostClient.create_post`.
- `CommandContext` already carries `channel_id` and `channel_type`, which enables current-channel
  affordances without changing the Mattermost event model.

## Evaluation Model

Each idea was scored from 1 to 10 using:

- expected UX impact for posting tasks;
- fit with Mattermost conventions and bot constraints;
- reduction in destructive or embarrassing posting mistakes;
- implementation size and operational risk;
- ability to test with the current repository shape.

Ideas below 8 were either narrowed or upgraded until they reached 8+.

| Area | Initial Idea | Initial Score | Improved Proposal | Final Score |
| --- | --- | ---: | --- | ---: |
| Bot flow | Shorter `!send` command | Already done | Build on defaults with preview and next actions | 8.6 |
| Bot flow | Long setup wizard | 7.4 | Adaptive `!setup` / `!next` checklist with one next action | 8.3 |
| Bot flow | Better `!draft show` | 7.6 | Validated publish preview with target readiness and exact send command | 8.6 |
| Bot flow | Manual channel alias entry | 8.0 | Add current Mattermost channel by alias from the channel itself | 8.8 |
| Web UI | Standalone composer | 8.5 | Composer plus review, target validation, draft queue, and audit context | 9.4 |
| Web UI | Target settings page | 8.1 | Targets dashboard with default readiness, manual ID entry, and add-current hint | 8.5 |
| Web UI | Scheduling | 7.2 | Phase 3 scheduled drafts with timezone, cancel/reschedule, worker, and audit | 8.1 |

## Goals

- Reduce memory burden around commands, draft IDs, bot aliases, and channel aliases.
- Make the current posting target visible before a post is published.
- Prevent common posting mistakes before calling the Mattermost create post API.
- Provide a scan-friendly web workspace for drafts, targets, and audit history.
- Keep the existing command flow working for power users.
- Reuse existing database concepts: users, posting bots, channel aliases, defaults, drafts, audit log.
- Preserve token secrecy: no UI or log path may show stored posting bot token material.

## Non-Goals

- No automatic creation of Mattermost bot accounts in the first UI/UX pass.
- No replacement of the existing Mattermost bot command surface.
- No public landing page.
- No unauthenticated web dashboard.
- No scheduling in the initial web UI phase.
- No large plugin rewrite before proving the simpler bot and web flows.

## Approach Comparison

### Approach 1: Conversational UX Polish

Improve the current Mattermost experience without adding a web server.

Includes:

- contextual state cards after important commands;
- `!setup` and `!next`;
- `@postbot !channel add-current <alias>`;
- publish preview in `!draft show <draft_id>`;
- recovery-oriented error messages.

Score: 8.7.

Trade-offs:

- Fastest path to value.
- Low operational risk.
- Still limited by text commands and chat chronology.
- Cannot provide true buttons or dialogs without an inbound HTTP surface.

### Approach 2: Mattermost Hybrid

Add interactive messages, buttons, menus, and dialogs inside Mattermost.

Score: 8.4.

Trade-offs:

- Good fit for confirmation, target selection, and one-click actions.
- Requires a new inbound HTTP endpoint or Mattermost plugin path.
- Adds security work for action signatures/tokens and user authorization.
- Less valuable if a web UI is already planned, because both need similar backend endpoints.

### Approach 3: Web UI Companion

Add a web interface for composition, target management, draft review, and audit.

Score: 9.1.

Trade-offs:

- Best workspace for repeated posting tasks and multi-draft workflows.
- More implementation surface: auth, server routes, UI, session handling, CSRF protection.
- Needs careful integration with existing bot ownership and approval rules.
- Can later power Mattermost buttons/dialogs through the same backend services.

Recommendation: implement Approach 1 first, then Approach 3. Treat Approach 2 as a later thin
Mattermost convenience layer once the backend has web endpoints and hardened action handling.

## Phase 1: Current Bot UX

### State Cards

Replace terse success replies with compact state-oriented replies where helpful.

Examples:

- after saving a draft;
- after setting or showing defaults;
- after listing drafts;
- after setup checks.

Draft save response should include:

- draft ID;
- first-line preview;
- current default target if valid;
- exact publish command;
- exact preview command.

Example shape:

```text
Draft #12 saved.
Preview: Quarterly release notes...
Target: bot news, channel town
Next: !draft show 12
Publish: !send 12
```

For users without defaults, the state card should show the explicit send form and a default setup
command.

### `!setup` And `!next`

Add two DM commands for approved and unapproved users:

```text
!setup
!next
```

`!setup` returns a concise checklist:

- registration status;
- whether the user has at least one posting bot alias;
- whether the user has at least one channel alias;
- whether a valid default target exists;
- whether there are saved drafts;
- the next recommended command.

`!next` returns only the next recommended command and one sentence of context.

This keeps onboarding discoverable without forcing a long wizard state machine.

### Current Channel Alias

Add:

```text
@postbot !channel add-current <alias>
```

Rules:

- Only works in non-DM Mattermost channels.
- Requires an approved user.
- Saves `ctx.channel_id` as a channel alias owned by the caller.
- Rejects duplicate aliases consistently with `!channel add`.
- Responds in the channel with a short confirmation that does not expose private tokens.

This removes the need to copy a Mattermost channel ID for the common case.

### Publish Preview

Upgrade:

```text
!draft show <draft_id>
```

The reply should include:

- full draft message;
- draft ID;
- effective target if defaults are valid;
- warnings if defaults are missing or stale;
- exact command to publish;
- exact command to delete.

This command should not publish. It is a safe review surface before a high-cost action.

### Recovery-Oriented Errors

Keep error text short, but include one next action.

Examples:

- missing default target: show `!default set --bot <alias> --channel <channel_alias>` and `!bot list`
  / `!channel list`;
- unknown bot: suggest `!bot list`;
- unknown channel alias: suggest `!channel list` or `@postbot !channel add-current <alias>`;
- stale default: suggest `!default clear` or a new `!default set ...`;
- draft unavailable: suggest `!draft list`.

## Phase 2: Web UI Companion

### Product Shape

The first web screen is the posting workspace, not a landing page.

Primary navigation:

- Composer;
- Drafts;
- Targets;
- Audit.

The UI should be quiet and operational: dense enough to scan, with clear validation and restrained
visual styling. It should avoid marketing-style hero sections.

### Authentication

Use one-time login links initiated from Mattermost DM:

```text
!web
```

Flow:

1. Approved user sends `!web` in DM.
2. Bot creates a short-lived login token bound to Mattermost `user_id`.
3. Bot replies with a web login URL.
4. User opens the URL and receives a web session.
5. Token is single-use and expires quickly.

This avoids asking users for Mattermost passwords and keeps identity anchored to the existing bot
approval model.

### Composer View

Composer provides:

- multiline post editor;
- markdown preview;
- bot selector;
- channel selector;
- default target indicator;
- save draft;
- review/publish action;
- validation before publish.

The composer supports both new drafts and editing existing unsent drafts.

Publishing from the composer should use the same service path as `!send`: resolve target, decrypt
the selected posting bot token, call Mattermost, mark the draft sent, and record audit.

### Drafts View

Drafts list should show:

- draft ID;
- status;
- first-line preview;
- created timestamp;
- target readiness;
- actions: open, edit, publish, delete.

Opening a draft shows the full message, target selection, validation, and audit-relevant metadata.

### Targets View

Targets view should show:

- posting bot aliases;
- channel aliases;
- current default pair;
- whether each default dependency is valid;
- actions to set or clear default.

Adding bot tokens must keep token input write-only. After submission, the UI should show only alias,
validated bot username, and status.

Channel alias creation should support:

- manual channel ID entry;
- a visible hint to use `@postbot !channel add-current <alias>` from Mattermost when the user wants
  to bind the current channel without copying an ID.

Dynamic Mattermost channel lookup is deferred to Phase 3 because it depends on server permissions and
can be added later without changing the target model.

### Audit View

Audit view should show:

- created timestamp;
- caller username;
- draft ID;
- bot username/alias;
- channel alias and resolved channel ID;
- status;
- Mattermost post ID for successful sends;
- safe error code/message for failed sends.

The view is read-only in Phase 2.

## Phase 3: Interactive Mattermost And Scheduling

### Mattermost Interactive Layer

After the web backend exists, Mattermost buttons and dialogs can be added for:

- publish from a draft preview;
- delete draft;
- set default target;
- choose target in a dialog.

Action requests must validate:

- action token or signature;
- Mattermost user ID;
- draft ownership;
- user approval status;
- target ownership.

### Scheduling

Scheduled drafts should wait until Phase 3.

Minimum viable scheduling:

- schedule a saved draft for an exact date/time with timezone;
- show scheduled status in Drafts;
- cancel or reschedule before send time;
- worker publishes due drafts through the same send service;
- all attempts are audited.

No recurring schedules in the first scheduling version.

## Architecture

### Shared Domain Services

Introduce service functions before adding web routes:

- draft creation and update;
- target resolution;
- publish draft;
- setup state calculation;
- audit listing.

The existing command handlers and new web routes should call the same services. This prevents web
publishing and bot publishing from drifting apart.

### Bot Layer

The bot layer remains responsible for:

- parsing Mattermost messages;
- enforcing DM/channel command constraints;
- translating service outcomes into localized Mattermost replies;
- sending posts through the manager bot.

### Web Layer

The web layer should be added as a separate module, for example `src/mm_post_bot/web`.

Responsibilities:

- session authentication from one-time login tokens;
- CSRF protection for state-changing forms;
- HTML pages and form handlers or JSON endpoints;
- mapping service errors to user-visible validation states.

Use a Python-first server-rendered web UI:

- FastAPI as the ASGI framework;
- Jinja2 templates for HTML;
- regular HTML forms for state-changing actions;
- small progressive enhancements only where they remove friction.

The web app should run as a separate process from the WebSocket bot, using the same package, Docker
image, database, and settings style. Add a script entry point such as `mm-post-bot-web` and a compose
service that starts the web process. This keeps bot reconnect behavior independent from web request
serving while avoiding a second codebase.

### Data Model Additions

Add:

- one-time web login token table;
- signed web session cookie secret in configuration;
- draft `updated_at` support for web editing;
- scheduled draft fields/table in Phase 3 only.

No new table should duplicate posting bot token material.

Use signed HTTP-only cookies for web sessions. Do not add a server-side session table in Phase 2.

## Error Handling

User-facing errors should:

- state what failed in plain language;
- avoid Mattermost internals unless useful;
- include exactly one or two next actions;
- never expose tokens;
- distinguish validation failures from publish failures.

Publish failures should still record audit entries when enough target context is known.

Web form errors should appear next to the affected field when possible. Global errors should be used
for API or permission failures.

## Security And Privacy

- Posting bot tokens remain encrypted at rest.
- Token inputs are write-only.
- One-time web login links expire and cannot be reused.
- Web sessions are bound to approved Mattermost users.
- State-changing web requests require CSRF protection.
- All publish paths enforce draft ownership and approved-user status.
- Action URLs for Mattermost buttons/dialogs must use unguessable action IDs or signatures.
- Audit views must not expose message hashes as a replacement for safe user-facing details.

## Testing

Phase 1 command tests:

- `!setup` for unregistered, pending, blocked, approved partially configured, and fully configured
  users;
- `!next` returns the correct next action;
- `@postbot !channel add-current <alias>` saves the current channel ID;
- add-current rejects DMs, duplicate aliases, and unapproved users;
- draft save replies include target/next-action context;
- `!draft show <id>` includes target readiness and publish/delete commands;
- recovery messages include relevant next actions in English and Russian.

Phase 2 tests:

- one-time login token creation, expiry, single-use behavior, and user binding;
- web access rejects unauthenticated and non-approved users;
- composer creates, edits, and publishes drafts through the shared publish service;
- targets page validates bot token and channel alias inputs;
- draft list and audit list are owner-scoped;
- CSRF protection covers state-changing requests;
- no response includes stored token ciphertext or plaintext.

Verification:

- `uv run pytest -p no:cacheprovider`;
- focused tests for new commands and web routes;
- browser smoke test for the web UI once implemented.

## Rollout

1. Ship Phase 1 bot UX improvements behind normal command tests.
2. Document the improved commands in `README.md`.
3. Add Phase 2 web UI with a minimal server-rendered interface.
4. Keep bot commands and web UI interoperable through shared services.
5. Add interactive Mattermost actions only after web auth and action handling are hardened.
6. Add scheduling only after normal immediate publishing is stable in both bot and web paths.

## Decisions For Implementation Planning

- Phase 1 is implemented before Phase 2.
- Phase 2 uses FastAPI and Jinja2, served by a separate web process from the bot.
- Phase 2 uses one-time login links from Mattermost DM and signed HTTP-only session cookies.
- Phase 2 includes draft editing in the web UI.
- Phase 2 uses manual channel ID entry plus the bot `add-current` command; dynamic channel search is
  Phase 3.
- Phase 3 is split into two independent follow-up specs if both interactive Mattermost actions and
  scheduling are pursued.
