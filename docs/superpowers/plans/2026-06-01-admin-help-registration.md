# Admin Help And Registration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `!help` clear for configured admins before and after registration, and make admin registration messaging explicit without breaking approval requests to unregistered admins.

**Architecture:** Keep authorization for admin commands based on `MM_ADMINS`, not on `app_user` registration. Split help output into status-aware sections, showing admin commands to configured admins even when they are not registered, while showing posting commands only to users with `status='approved'`. Keep ordinary user registration notifications going to all configured admins via Mattermost username lookup, regardless of whether those admins exist in the local DB.

**Tech Stack:** Python 3.14, pytest, Mattermost command handlers, existing `UserRepo` and `CommandContext`.

---

### Task 1: Help Behavior For Configured Admins

**Files:**
- Modify: `tests/test_commands.py`
- Modify: `src/mm_post_bot/commands/help.py`

- [ ] **Step 1: Write failing tests for unregistered configured admin help**

Add this test near existing help tests in `tests/test_commands.py`:

```python
async def test_help_shows_admin_bootstrap_for_unregistered_configured_admin(
    ctx: CommandFixture,
):
    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!help",
    )

    assert reply is not None
    assert "Admin bootstrap" in reply
    assert "configured as an admin" in reply
    assert "Run !register" in reply
    assert "!user approve <username|user_id>" in reply
    assert "!bot add" not in reply
    assert "!send" not in reply
```

Add this test to ensure mention-style names still work:

```python
async def test_help_shows_admin_bootstrap_for_mention_style_configured_admin(
    ctx: CommandFixture,
):
    reply = await dispatch(
        ctx.make("admin-id", "@admin", admin_usernames={"admin"}),
        "!help",
    )

    assert reply is not None
    assert "Admin bootstrap" in reply
    assert "!user approve <username|user_id>" in reply
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_commands.py::test_help_shows_admin_bootstrap_for_unregistered_configured_admin tests/test_commands.py::test_help_shows_admin_bootstrap_for_mention_style_configured_admin -q
```

Expected: both tests fail because current `!help` shows admin commands but no `Admin bootstrap` text.

- [ ] **Step 3: Implement structured help sections**

Replace the body of `src/mm_post_bot/commands/help.py` with section-based helpers:

```python
from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    username = ctx.caller_username.lstrip("@")
    user_status = _caller_status(ctx)
    is_configured_admin = username in ctx.admin_usernames
    sections = [
        _section(
            "Core",
            [
                "!help - show available commands",
                "!register - register for posting access",
                "!status - show your registration status",
            ],
        )
    ]

    if is_configured_admin and user_status != "approved":
        sections.append(
            _section(
                "Admin bootstrap",
                [
                    "You are configured as an admin in MM_ADMINS.",
                    "You can approve registration requests now.",
                    "Run !register to activate your local admin account and enable posting commands.",
                ],
            )
        )

    if user_status == "pending":
        sections.append(_section("Registration", ["Your account is pending approval."]))
    elif user_status == "blocked":
        sections.append(_section("Registration", ["Your access is blocked. Contact an admin."]))
    elif user_status == "approved":
        sections.extend(_approved_user_sections())
    elif not is_configured_admin:
        sections.append(_section("Registration", ["Run !register to request posting access."]))

    if is_configured_admin:
        sections.append(
            _section(
                "Admin",
                [
                    "!user approve <username|user_id> - approve a user",
                    "!user block <username|user_id> - block a user",
                    "!user unblock <username|user_id> - unblock and approve a user",
                    "!user list [pending|approved|blocked] - list users",
                ],
            )
        )

    return "\n\n".join(sections)


def _approved_user_sections() -> list[str]:
    return [
        _section(
            "Posting bots",
            [
                "!bot add <alias> <token> - add a posting bot token",
                "!bot list - list your posting bots",
                "!bot remove <alias> - remove a posting bot",
            ],
        ),
        _section(
            "Channels",
            [
                "!channel add <alias> <channel_id> - add a channel alias",
                "!channel set <alias> <channel_id> - update a channel alias",
                "!channel remove <alias> - remove a channel alias",
                "!channel list - list your channel aliases",
                "!channel show <alias> - show a channel alias",
            ],
        ),
        _section(
            "Drafts",
            [
                "!draft - capture your next DM as a draft",
                "!draft cancel - cancel active draft capture",
                "!draft list - list saved drafts",
                "!draft show <draft_id> - show a saved draft",
                "!draft delete <draft_id> - delete a saved draft",
            ],
        ),
        _section(
            "Publishing",
            ["!send <draft_id> --bot <alias> --channel <channel_alias> - publish a draft"],
        ),
    ]


def _section(title: str, rows: list[str]) -> str:
    return "\n".join([f"{title}:", *rows])


def _caller_status(ctx: CommandContext) -> str | None:
    try:
        return ctx.user_repo.get(ctx.caller_user_id).status
    except LookupError:
        return None
```

- [ ] **Step 4: Run focused help tests**

Run:

```bash
uv run pytest tests/test_commands.py::test_help_shows_admin_bootstrap_for_unregistered_configured_admin tests/test_commands.py::test_help_shows_admin_bootstrap_for_mention_style_configured_admin tests/test_commands.py::test_help_changes_after_user_approval tests/test_commands.py::test_help_keeps_posting_commands_from_blocked_user tests/test_commands.py::test_help_shows_admin_commands_for_mention_style_admin -q
```

Expected: all listed tests pass.

- [ ] **Step 5: Commit help change**

Run:

```bash
git add src/mm_post_bot/commands/help.py tests/test_commands.py
git commit -m "feat: clarify admin help output"
```

### Task 2: Admin Registration Messaging

**Files:**
- Modify: `tests/test_commands.py`
- Modify: `src/mm_post_bot/commands/register.py`

- [ ] **Step 1: Write failing tests for explicit admin registration response**

Replace or extend `test_admin_registers_as_approved` in `tests/test_commands.py`:

```python
async def test_admin_registers_as_approved_with_bootstrap_message(ctx: CommandFixture):
    reply = await dispatch(ctx.make("admin-id", "admin", admin_usernames={"admin"}), "!register")

    assert reply is not None
    assert "Registered admin as admin" in reply
    assert "approved automatically" in reply
    assert "MM_ADMINS" in reply
    assert ctx.users.get("admin-id").role == "admin"
    assert ctx.users.get("admin-id").status == "approved"
    assert ctx.manager_mm.posts == []
```

Update `test_admin_registers_as_approved_with_mention_style_username`:

```python
async def test_admin_registers_as_approved_with_mention_style_username(ctx: CommandFixture):
    reply = await dispatch(ctx.make("admin-id", "@admin", admin_usernames={"admin"}), "!register")

    assert reply is not None
    assert "Registered admin as admin" in reply
    assert "approved automatically" in reply
    assert ctx.users.get("admin-id").username == "admin"
    assert ctx.users.get("admin-id").role == "admin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run:

```bash
uv run pytest tests/test_commands.py::test_admin_registers_as_approved_with_bootstrap_message tests/test_commands.py::test_admin_registers_as_approved_with_mention_style_username -q
```

Expected: tests fail because current response is generic: `Registered admin as admin. Current status: approved.`

- [ ] **Step 3: Update `register.handle` response only for configured admins**

Modify `src/mm_post_bot/commands/register.py`:

```python
async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    username = ctx.caller_username.lstrip("@")
    is_admin = username in ctx.admin_usernames
    user = ctx.user_repo.upsert_seen_user(
        user_id=ctx.caller_user_id,
        username=username,
        is_admin=is_admin,
    )
    if is_admin:
        return (
            f"Registered {user.username} as admin.\n"
            "Your access is approved automatically because your username is configured "
            "in MM_ADMINS.\n"
            "You can approve users and use posting commands."
        )

    await _notify_admins(ctx, username=username)
    return f"Registered {user.username} as {user.role}. Current status: {user.status}."
```

Do not change `_notify_admins`; ordinary user registration must still notify configured admins even when those admins do not exist in `app_user`.

- [ ] **Step 4: Run focused registration tests**

Run:

```bash
uv run pytest tests/test_commands.py::test_register_notifies_configured_admins tests/test_commands.py::test_register_notification_failures_do_not_block_registration tests/test_commands.py::test_admin_registers_as_approved_with_bootstrap_message tests/test_commands.py::test_admin_registers_as_approved_with_mention_style_username -q
```

Expected: all listed tests pass; `test_register_notifies_configured_admins` confirms unregistered configured admins still receive approval requests via Mattermost lookup.

- [ ] **Step 5: Commit registration messaging**

Run:

```bash
git add src/mm_post_bot/commands/register.py tests/test_commands.py
git commit -m "feat: clarify configured admin registration"
```

### Task 3: Admin Command Access Contract

**Files:**
- Modify: `tests/test_commands.py`
- No production change expected unless the test fails.

- [ ] **Step 1: Add regression test that configured admin can approve without local registration**

Add this test near existing admin tests:

```python
async def test_configured_admin_can_approve_without_local_registration(ctx: CommandFixture):
    await dispatch(ctx.make("alice-id", "alice"), "!register")

    reply = await dispatch(
        ctx.make("admin-id", "admin", admin_usernames={"admin"}),
        "!user approve alice",
    )

    assert reply is not None
    assert "Approved alice" in reply
    assert ctx.users.get("alice-id").status == "approved"
    with pytest.raises(LookupError):
        ctx.users.get("admin-id")
```

- [ ] **Step 2: Run the regression test**

Run:

```bash
uv run pytest tests/test_commands.py::test_configured_admin_can_approve_without_local_registration -q
```

Expected: test passes with current production code because admin access is based on `ctx.admin_usernames`.

- [ ] **Step 3: Commit access regression test**

Run:

```bash
git add tests/test_commands.py
git commit -m "test: lock configured admin approval bootstrap"
```

### Task 4: Documentation Updates

**Files:**
- Modify: `README.md`
- Test: no dedicated test file; verify with `rg`.

- [ ] **Step 1: Update README admin registration section**

In `README.md`, add this subsection inside `## Команды`, immediately after the admin command code block and before `Как работает draft-first flow`:

```markdown
### Администраторы из MM_ADMINS

Пользователь, чей username указан в `MM_ADMINS`, считается configured admin даже до локальной
регистрации в `app_user`. Такой админ уже может получать заявки на регистрацию и выполнять
`!user approve`, `!user block`, `!user unblock`, `!user list`.

Чтобы использовать posting-команды (`!bot`, `!channel`, `!draft`, `!send`), configured admin
должен один раз выполнить `!register`. После этого локальная запись создается сразу со статусом
`approved` и ролью `admin`; дополнительный approval не нужен.
```

- [ ] **Step 2: Verify docs mention the intended contract**

Run:

```bash
rg -n "configured admin|MM_ADMINS|posting-команды|approved" README.md
```

Expected: output includes the new subsection and no statement says admins must register before receiving approval requests.

- [ ] **Step 3: Commit documentation**

Run:

```bash
git add README.md
git commit -m "docs: explain configured admin bootstrap"
```

### Task 5: Final Verification And MR Update

**Files:**
- Review all modified files.

- [ ] **Step 1: Run full verification**

Run:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy
uv run pytest -q
```

Expected:

```text
All checks passed!
29 files already formatted
Success: no issues found in 22 source files
124 passed
```

- [ ] **Step 2: Inspect final diff and history**

Run:

```bash
git status --short
git log --oneline -6
```

Expected: clean worktree and recent commits for help, registration, regression test, and docs.

- [ ] **Step 3: Push branch**

Run:

```bash
git push origin ai/mattermost-post-bot-mvp
```

Expected: branch updates MR `!2`.

- [ ] **Step 4: Verify MR is still mergeable**

Run:

```bash
glab mr view 2 --output json
```

Expected fields:

```json
{
  "detailed_merge_status": "mergeable",
  "has_conflicts": false
}
```
