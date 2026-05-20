from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    try:
        user = ctx.user_repo.get(ctx.caller_user_id)
    except LookupError:
        return "You are not registered yet. Run !register to request access."
    return f"{user.username} is {user.status} as {user.role}."
