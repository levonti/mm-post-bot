from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def add(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 2:
        return ctx.t("channel.add_usage")

    alias, channel_id = args.positional
    channel_id_error = _validate_channel_id(ctx, channel_id)
    if channel_id_error is not None:
        return channel_id_error

    try:
        ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        pass
    else:
        return ctx.t("channel.duplicate", alias=alias)

    channel = ctx.user_channel_repo.add(
        owner_user_id=ctx.caller_user_id,
        alias=alias,
        channel_id=channel_id,
    )
    return ctx.t("channel.added", alias=channel.alias)


async def set_channel(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 2:
        return ctx.t("channel.set_usage")

    alias, channel_id = args.positional
    channel_id_error = _validate_channel_id(ctx, channel_id)
    if channel_id_error is not None:
        return channel_id_error

    try:
        ctx.user_channel_repo.update_channel_id(
            ctx.caller_user_id,
            alias,
            channel_id=channel_id,
        )
    except LookupError:
        return ctx.t("channel.not_found", alias=alias)
    return ctx.t("channel.updated", alias=alias)


async def remove(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 1:
        return ctx.t("channel.remove_usage")

    alias = args.positional[0]
    try:
        ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        return ctx.t("channel.not_found", alias=alias)

    ctx.user_channel_repo.soft_delete(ctx.caller_user_id, alias)
    return ctx.t("channel.removed", alias=alias)


async def list_channels(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if args.positional:
        return ctx.t("channel.list_usage")

    channels = ctx.user_channel_repo.list_for_owner(ctx.caller_user_id)
    if not channels:
        return ctx.t("channel.list_empty")

    return "\n".join(f"{channel.alias} - {channel.channel_id}" for channel in channels)


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 1:
        return ctx.t("channel.show_usage")

    alias = args.positional[0]
    try:
        channel = ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        return ctx.t("channel.not_found", alias=alias)
    return f"{channel.alias} - {channel.channel_id}"


def _require_channel_command_access(ctx: CommandContext) -> str | None:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error
    if ctx.channel_type != "D":
        return ctx.t("channel.dm_only")
    return None


def _validate_channel_id(ctx: CommandContext, channel_id: str) -> str | None:
    if not channel_id:
        return ctx.t("channel.add_usage")
    if channel_id.startswith(("http://", "https://")):
        return ctx.t("channel.id_not_link")
    return None
