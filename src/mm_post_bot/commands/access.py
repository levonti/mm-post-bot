from .context import CommandContext


def require_approved_user(ctx: CommandContext) -> str | None:
    try:
        user = ctx.user_repo.get(ctx.caller_user_id)
    except LookupError:
        return ctx.t("access.not_registered")

    if user.status == "approved":
        return None
    if user.status == "blocked":
        return ctx.t("access.blocked")
    return ctx.t("access.pending")
