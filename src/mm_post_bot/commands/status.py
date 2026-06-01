from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    try:
        user = ctx.user_repo.get(ctx.caller_user_id)
    except LookupError:
        return ctx.t("access.not_registered_status")
    return ctx.t("status.line", username=user.username, status=user.status, role=user.role)
