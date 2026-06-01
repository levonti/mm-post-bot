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
                    "Run !register to activate your local admin account and enable "
                    "posting commands.",
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
