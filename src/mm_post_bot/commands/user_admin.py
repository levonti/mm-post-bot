from mm_post_bot.repository import AppUser

from .context import CommandContext
from .parser import ParsedArgs

VALID_STATUSES = frozenset({"pending", "approved", "blocked"})


def _is_admin(ctx: CommandContext) -> bool:
    return ctx.caller_username in ctx.admin_usernames


def _require_admin(ctx: CommandContext) -> str | None:
    if _is_admin(ctx):
        return None
    return "Only admins can use this command."


def _resolve_user(ctx: CommandContext, target: str) -> AppUser | None:
    try:
        return ctx.user_repo.get_by_username(target)
    except LookupError:
        pass

    try:
        return ctx.user_repo.get(target)
    except LookupError:
        return None


def _target_arg(args: ParsedArgs) -> str | None:
    if not args.positional:
        return None
    return args.positional[0]


async def approve(ctx: CommandContext, args: ParsedArgs) -> str:
    admin_error = _require_admin(ctx)
    if admin_error is not None:
        return admin_error

    target = _target_arg(args)
    if target is None:
        return "Usage: !user approve <username|user_id>"

    user = _resolve_user(ctx, target)
    if user is None:
        return f"Could not find user {target}."

    approved = ctx.user_repo.approve(user.user_id, approved_by=ctx.caller_user_id)
    return f"Approved {approved.username} ({approved.user_id})."


async def block(ctx: CommandContext, args: ParsedArgs) -> str:
    admin_error = _require_admin(ctx)
    if admin_error is not None:
        return admin_error

    target = _target_arg(args)
    if target is None:
        return "Usage: !user block <username|user_id>"

    user = _resolve_user(ctx, target)
    if user is None:
        return f"Could not find user {target}."

    blocked = ctx.user_repo.block(user.user_id, blocked_by=ctx.caller_user_id)
    return f"Blocked {blocked.username} ({blocked.user_id})."


async def unblock(ctx: CommandContext, args: ParsedArgs) -> str:
    admin_error = _require_admin(ctx)
    if admin_error is not None:
        return admin_error

    target = _target_arg(args)
    if target is None:
        return "Usage: !user unblock <username|user_id>"

    user = _resolve_user(ctx, target)
    if user is None:
        return f"Could not find user {target}."

    approved = ctx.user_repo.unblock(user.user_id, approved_by=ctx.caller_user_id)
    return f"Unblocked and approved {approved.username} ({approved.user_id})."


async def list_users(ctx: CommandContext, args: ParsedArgs) -> str:
    admin_error = _require_admin(ctx)
    if admin_error is not None:
        return admin_error

    status = args.positional[0] if args.positional else None
    if status is not None and status not in VALID_STATUSES:
        return "Status must be one of: pending, approved, blocked."

    users = ctx.user_repo.list_by_status(status)
    if not users:
        suffix = f" with status {status}" if status is not None else ""
        return f"No users{suffix}."

    rows = [f"{user.username} ({user.user_id}) - {user.role}, {user.status}" for user in users]
    return "\n".join(rows)
