from ..services.posting import PublishDraftRequest, PublishError, TargetRequest, publish_draft
from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    parsed = _parse_args(args)
    if parsed is None:
        return ctx.t("send.usage")

    draft_id, requested_bot_alias, requested_channel_alias = parsed
    try:
        result = await publish_draft(
            ctx,
            PublishDraftRequest(
                draft_id=draft_id,
                target=TargetRequest(
                    bot_alias=requested_bot_alias,
                    channel_alias=requested_channel_alias,
                ),
            ),
        )
    except PublishError as exc:
        return ctx.t(exc.message_key)
    return ctx.t("send.published", draft_id=result.draft_id)


def _parse_args(args: ParsedArgs) -> tuple[int, str | None, str | None] | None:
    if len(args.positional) != 1 or not set(args.flags).issubset({"bot", "channel"}):
        return None

    bot_alias = args.flags.get("bot")
    channel_alias = args.flags.get("channel")
    if bot_alias is not None and (not isinstance(bot_alias, str) or not bot_alias):
        return None
    if channel_alias is not None and (not isinstance(channel_alias, str) or not channel_alias):
        return None

    try:
        draft_id = int(args.positional[0])
    except ValueError:
        return None
    if draft_id <= 0:
        return None

    return draft_id, bot_alias, channel_alias
