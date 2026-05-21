from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    username = ctx.caller_username.lstrip("@")
    is_admin = username in ctx.admin_usernames
    user = ctx.user_repo.upsert_seen_user(
        user_id=ctx.caller_user_id,
        username=username,
        is_admin=is_admin,
    )
    return f"Registered {user.username} as {user.role}. Current status: {user.status}."
