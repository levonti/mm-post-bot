from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_default_command_access(ctx)
    if access_error is not None:
        return access_error

    if args.positional or args.flags:
        return ctx.t("default.usage")

    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    if default is None:
        if ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id):
            return ctx.t("default.stale")
        return ctx.t("default.none")

    return ctx.t(
        "default.current",
        bot_alias=default.bot.alias,
        bot_username=default.bot.bot_username,
        channel_alias=default.channel.alias,
        channel_id=default.channel.channel_id,
    )


async def set_defaults(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_default_command_access(ctx)
    if access_error is not None:
        return access_error

    parsed = _parse_set_args(args)
    if parsed is None:
        return ctx.t("default.set_usage")

    bot_alias, channel_alias = parsed
    try:
        ctx.user_bot_repo.get_by_owner_and_alias(ctx.caller_user_id, bot_alias)
    except LookupError:
        return ctx.t("default.bot_not_found", alias=bot_alias)

    try:
        ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, channel_alias)
    except LookupError:
        return ctx.t("default.channel_not_found", alias=channel_alias)

    try:
        default = ctx.user_post_default_repo.set_for_owner(
            ctx.caller_user_id,
            bot_alias=bot_alias,
            channel_alias=channel_alias,
        )
    except LookupError:
        return ctx.t("default.stale")
    return ctx.t(
        "default.set",
        bot_alias=default.bot.alias,
        channel_alias=default.channel.alias,
    )


async def clear(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_default_command_access(ctx)
    if access_error is not None:
        return access_error

    if args.positional or args.flags:
        return ctx.t("default.clear_usage")

    ctx.user_post_default_repo.clear_for_owner(ctx.caller_user_id)
    return ctx.t("default.cleared")


def _require_default_command_access(ctx: CommandContext) -> str | None:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error
    if ctx.channel_type != "D":
        return ctx.t("default.dm_only")
    return None


def _parse_set_args(args: ParsedArgs) -> tuple[str, str] | None:
    if args.positional or set(args.flags) != {"bot", "channel"}:
        return None

    bot_alias = args.flags["bot"]
    channel_alias = args.flags["channel"]
    if not isinstance(bot_alias, str) or not bot_alias:
        return None
    if not isinstance(channel_alias, str) or not channel_alias:
        return None
    return bot_alias, channel_alias
