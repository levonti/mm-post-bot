from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    commands = [
        "!help - show available commands",
        "!register - register for posting access",
        "!status - show your registration status",
    ]

    status = _caller_status(ctx)
    if status == "approved":
        commands.extend(
            [
                "!bot add <alias> <token> - add a posting bot token",
                "!bot list - list your posting bots",
                "!bot remove <alias> - remove a posting bot",
                "!draft - capture your next DM as a draft",
                "!draft cancel - cancel active draft capture",
                "!draft list - list saved drafts",
                "!draft show <draft_id> - show a saved draft",
                "!draft delete <draft_id> - delete a saved draft",
                (
                    "!send <draft_id> --bot <alias> "
                    "--channel <mattermost-channel-link> - publish a draft"
                ),
            ]
        )

    if ctx.caller_username.lstrip("@") in ctx.admin_usernames:
        commands.extend(
            [
                "!user approve <username|user_id> - approve a user",
                "!user block <username|user_id> - block a user",
                "!user unblock <username|user_id> - unblock and approve a user",
                "!user list [pending|approved|blocked] - list users",
            ]
        )
    return "\n".join(commands)


def _caller_status(ctx: CommandContext) -> str | None:
    try:
        return ctx.user_repo.get(ctx.caller_user_id).status
    except LookupError:
        return None
