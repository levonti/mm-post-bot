from typing import Any

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
    if not is_admin:
        await _notify_admins(ctx, username=username)
    return f"Registered {user.username} as {user.role}. Current status: {user.status}."


async def _notify_admins(ctx: CommandContext, *, username: str) -> None:
    for admin_username in sorted(ctx.admin_usernames):
        try:
            admin = await ctx.manager_mm.get_user_by_username(admin_username)
            admin_user_id = _string_field(admin, "id")
            if admin_user_id is None:
                continue
            channel = await ctx.manager_mm.create_direct_channel(ctx.manager_user_id, admin_user_id)
            channel_id = _string_field(channel, "id")
            if channel_id is None:
                continue
            await ctx.manager_mm.create_post(
                channel_id,
                (
                    f"New registration request from {username} ({ctx.caller_user_id}).\n"
                    f"Approve with: !user approve {username}"
                ),
            )
        except Exception:
            continue


def _string_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    return None
