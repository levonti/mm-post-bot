from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def add(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 2:
        return "Usage: !channel add <alias> <channel_id>"

    alias, channel_id = args.positional
    channel_id_error = _validate_channel_id(channel_id)
    if channel_id_error is not None:
        return channel_id_error

    try:
        ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        pass
    else:
        return f"You already have a channel named {alias}. Use !channel set {alias} <channel_id>."

    channel = ctx.user_channel_repo.add(
        owner_user_id=ctx.caller_user_id,
        alias=alias,
        channel_id=channel_id,
    )
    return f"Added channel {channel.alias}."


async def set_channel(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 2:
        return "Usage: !channel set <alias> <channel_id>"

    alias, channel_id = args.positional
    channel_id_error = _validate_channel_id(channel_id)
    if channel_id_error is not None:
        return channel_id_error

    try:
        ctx.user_channel_repo.update_channel_id(
            ctx.caller_user_id,
            alias,
            channel_id=channel_id,
        )
    except LookupError:
        return f"Could not find a channel named {alias}."
    return f"Updated channel {alias}."


async def remove(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 1:
        return "Usage: !channel remove <alias>"

    alias = args.positional[0]
    try:
        ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        return f"Could not find a channel named {alias}."

    ctx.user_channel_repo.soft_delete(ctx.caller_user_id, alias)
    return f"Removed channel {alias}."


async def list_channels(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if args.positional:
        return "Usage: !channel list"

    channels = ctx.user_channel_repo.list_for_owner(ctx.caller_user_id)
    if not channels:
        return "No channels added yet."

    return "\n".join(f"{channel.alias} - {channel.channel_id}" for channel in channels)


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = _require_channel_command_access(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 1:
        return "Usage: !channel show <alias>"

    alias = args.positional[0]
    try:
        channel = ctx.user_channel_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        return f"Could not find a channel named {alias}."
    return f"{channel.alias} - {channel.channel_id}"


def _require_channel_command_access(ctx: CommandContext) -> str | None:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error
    if ctx.channel_type != "D":
        return "Please manage channel aliases in a direct message."
    return None


def _validate_channel_id(channel_id: str) -> str | None:
    if not channel_id:
        return "Usage: !channel add <alias> <channel_id>"
    if channel_id.startswith(("http://", "https://")):
        return "Please provide a Mattermost channel id, not a channel link."
    return None
