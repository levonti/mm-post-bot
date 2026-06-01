from typing import Any

import httpx

from ..mm_client import MattermostClient, MattermostError
from ..security import encrypt_token, fingerprint_token
from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def add(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    if ctx.channel_type != "D":
        return ctx.t("bot.dm_only")

    if len(args.positional) != 2:
        return ctx.t("bot.add_usage")

    alias, token = args.positional
    try:
        ctx.user_bot_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        pass
    else:
        return ctx.t("bot.duplicate", alias=alias)

    client = MattermostClient(ctx.mm_rest_base, token, verify_ssl=ctx.mm_verify_ssl)
    try:
        me = await client.get_me()
    except MattermostError, httpx.HTTPError, ValueError:
        return ctx.t("bot.validate_failed")
    finally:
        await client.aclose()

    if me.get("is_bot") is not True:
        return ctx.t("bot.regular_user_token")

    bot_user_id = _string_field(me, "id")
    bot_username = _string_field(me, "username")
    if bot_user_id is None or bot_username is None:
        return ctx.t("bot.validate_failed")

    try:
        token_ciphertext = encrypt_token(token, ctx.token_encryption_key)
    except ValueError:
        return ctx.t("bot.storage_misconfigured")

    bot = ctx.user_bot_repo.add(
        owner_user_id=ctx.caller_user_id,
        alias=alias,
        bot_user_id=bot_user_id,
        bot_username=bot_username,
        bot_display_name=_string_field(me, "display_name"),
        token_ciphertext=token_ciphertext,
        token_fingerprint=fingerprint_token(token),
    )

    return ctx.t("bot.added", alias=bot.alias, bot_username=bot.bot_username)


async def list_bots(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    bots = ctx.user_bot_repo.list_for_owner(ctx.caller_user_id)
    if not bots:
        return ctx.t("bot.list_empty")

    return "\n".join(f"{bot.alias} - {bot.bot_username}" for bot in bots)


async def remove(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    if len(args.positional) != 1:
        return ctx.t("bot.remove_usage")

    alias = args.positional[0]
    try:
        ctx.user_bot_repo.get_by_owner_and_alias(ctx.caller_user_id, alias)
    except LookupError:
        return ctx.t("bot.not_found", alias=alias)

    ctx.user_bot_repo.soft_delete(ctx.caller_user_id, alias)
    return ctx.t("bot.removed", alias=alias)


def _string_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    return None
