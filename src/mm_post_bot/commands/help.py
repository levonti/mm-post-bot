from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    commands = [
        "!help - show available commands",
        "!register - register for posting access",
        "!status - show your registration status",
    ]
    if ctx.caller_username in ctx.admin_usernames:
        commands.extend(
            [
                "!user approve <username|user_id> - approve a user",
                "!user block <username|user_id> - block a user",
                "!user unblock <username|user_id> - unblock and approve a user",
                "!user list [pending|approved|blocked] - list users",
            ]
        )
    return "\n".join(commands)
