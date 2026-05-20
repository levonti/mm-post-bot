from .context import CommandContext


def require_approved_user(ctx: CommandContext) -> str | None:
    try:
        user = ctx.user_repo.get(ctx.caller_user_id)
    except LookupError:
        return "You are not registered yet. Run !register to request approval."

    if user.status == "approved":
        return None
    if user.status == "blocked":
        return "Your access is blocked. Contact an admin for help."
    return "Your account is pending approval. Please wait for an admin to approve you."
