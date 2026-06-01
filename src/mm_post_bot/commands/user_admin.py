from mm_post_bot.repository import AppUser

from ..i18n import recipient_locale, translate
from .context import CommandContext
from .parser import ParsedArgs

VALID_STATUSES = frozenset({"pending", "approved", "blocked"})


def _is_admin(ctx: CommandContext) -> bool:
    return ctx.caller_username.lstrip("@") in ctx.admin_usernames


def _require_admin(ctx: CommandContext) -> str | None:
    if _is_admin(ctx):
        return None
    return ctx.t("user.admin_only")


def _resolve_user(ctx: CommandContext, target: str) -> AppUser | None:
    target = target.lstrip("@")
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
        return ctx.t("user.approve_usage")

    user = _resolve_user(ctx, target)
    if user is None:
        return ctx.t("user.not_found", target=target)

    approved = ctx.user_repo.approve(user.user_id, approved_by=ctx.caller_user_id)
    await _notify_user_status(ctx, approved, message_key="user.notify_approved")
    return ctx.t("user.approved", username=approved.username, user_id=approved.user_id)


async def block(ctx: CommandContext, args: ParsedArgs) -> str:
    admin_error = _require_admin(ctx)
    if admin_error is not None:
        return admin_error

    target = _target_arg(args)
    if target is None:
        return ctx.t("user.block_usage")

    user = _resolve_user(ctx, target)
    if user is None:
        return ctx.t("user.not_found", target=target)
    if user.username.lstrip("@") in ctx.admin_usernames:
        return ctx.t("user.configured_admin_block")

    blocked = ctx.user_repo.block(user.user_id, blocked_by=ctx.caller_user_id)
    await _notify_user_status(ctx, blocked, message_key="user.notify_blocked")
    return ctx.t("user.blocked", username=blocked.username, user_id=blocked.user_id)


async def unblock(ctx: CommandContext, args: ParsedArgs) -> str:
    admin_error = _require_admin(ctx)
    if admin_error is not None:
        return admin_error

    target = _target_arg(args)
    if target is None:
        return ctx.t("user.unblock_usage")

    user = _resolve_user(ctx, target)
    if user is None:
        return ctx.t("user.not_found", target=target)

    approved = ctx.user_repo.unblock(user.user_id, approved_by=ctx.caller_user_id)
    await _notify_user_status(ctx, approved, message_key="user.notify_unblocked")
    return ctx.t("user.unblocked", username=approved.username, user_id=approved.user_id)


async def list_users(ctx: CommandContext, args: ParsedArgs) -> str:
    admin_error = _require_admin(ctx)
    if admin_error is not None:
        return admin_error

    status = args.positional[0] if args.positional else None
    if status is not None and status not in VALID_STATUSES:
        return ctx.t("user.invalid_status")

    users = ctx.user_repo.list_by_status(status)
    if not users:
        suffix = ctx.t("user.list_empty_suffix", status=status) if status is not None else ""
        return ctx.t("user.list_empty", suffix=suffix)

    rows = [f"{user.username} ({user.user_id}) - {user.role}, {user.status}" for user in users]
    return "\n".join(rows)


async def _notify_user_status(ctx: CommandContext, user: AppUser, *, message_key: str) -> None:
    try:
        channel = await ctx.manager_mm.create_direct_channel(ctx.manager_user_id, user.user_id)
        channel_id = _string_field(channel, "id")
        if channel_id is None:
            return
        locale = recipient_locale(
            ctx.user_preference_repo,
            user.user_id,
            default_locale=ctx.default_locale,
        )
        message = translate(locale, message_key)
        await ctx.manager_mm.create_post(channel_id, message)
    except Exception:
        return


def _string_field(payload: dict[str, object], field: str) -> str | None:
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    return None
