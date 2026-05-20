import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from typing import Any

import httpx

from ..channel_links import ChannelLink, ChannelLinkError, parse_channel_link
from ..db import transaction
from ..mm_client import MattermostClient, MattermostError
from ..repository import PostDraft, UserBot
from ..security import decrypt_token
from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs

USAGE = "Usage: !send <draft_id> --bot <alias> --channel <mattermost-channel-link>"
# Keep locks for the process lifetime so a draft lock is never replaced while waiters exist.
_SEND_LOCKS: dict[tuple[str, int], asyncio.Lock] = {}
_SEND_LOCKS_GUARD = asyncio.Lock()


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    parsed = _parse_args(args)
    if parsed is None:
        return USAGE

    draft_id, bot_alias, channel_link = parsed
    async with _send_lock(ctx.caller_user_id, draft_id):
        return await _send_locked(ctx, draft_id, bot_alias, channel_link)


async def _send_locked(
    ctx: CommandContext,
    draft_id: int,
    bot_alias: str,
    channel_link: str,
) -> str:
    try:
        draft = ctx.post_draft_repo.get_for_owner(ctx.caller_user_id, draft_id)
    except LookupError:
        return "Draft not found or unavailable."

    if draft.status != "draft":
        return "Draft not found or unavailable."

    try:
        bot = ctx.user_bot_repo.get_by_owner_and_alias(ctx.caller_user_id, bot_alias)
    except LookupError:
        return "Could not find that bot."

    try:
        token = decrypt_token(bot.token_ciphertext, ctx.token_encryption_key)
    except Exception:
        _record_failed_audit_safely(
            ctx,
            draft=draft,
            bot=bot,
            channel_link=channel_link,
            channel=None,
            resolved_channel_id=None,
            error_code="token_decrypt",
            error_message="Bot token storage is misconfigured.",
        )
        return "Bot token storage is misconfigured. Please contact an administrator."

    try:
        channel = parse_channel_link(channel_link, mm_url=ctx.mm_url)
    except ChannelLinkError:
        _record_failed_audit_safely(
            ctx,
            draft=draft,
            bot=bot,
            channel_link=channel_link,
            channel=None,
            resolved_channel_id=None,
            error_code="channel_link",
            error_message="Invalid Mattermost channel link.",
        )
        return "Could not understand that channel link. Please provide a Mattermost channel link."

    client = MattermostClient(ctx.mm_rest_base, token, verify_ssl=ctx.mm_verify_ssl)
    try:
        try:
            channel_payload = await client.get_channel_by_team_and_name(
                channel.team_name,
                channel.channel_name,
            )
            resolved_channel_id = _string_field(channel_payload, "id")
            if resolved_channel_id is None:
                raise ValueError("channel response did not include an id")
        except (MattermostError, httpx.HTTPError, ValueError) as exc:
            _record_failed_audit_safely(
                ctx,
                draft=draft,
                bot=bot,
                channel_link=channel_link,
                channel=channel,
                resolved_channel_id=None,
                error_code="mattermost_channel",
                error_message=_safe_error_message(exc),
            )
            return "Could not resolve that channel. Please check the channel link and bot access."

        try:
            post_payload = await client.create_post(resolved_channel_id, draft.message)
            mattermost_post_id = _string_field(post_payload, "id")
            if mattermost_post_id is None:
                raise ValueError("post response did not include an id")
        except (MattermostError, httpx.HTTPError, ValueError) as exc:
            _record_failed_audit_safely(
                ctx,
                draft=draft,
                bot=bot,
                channel_link=channel_link,
                channel=channel,
                resolved_channel_id=resolved_channel_id,
                error_code="mattermost_post",
                error_message=_safe_error_message(exc),
            )
            return "Could not publish the post. Please check bot permissions and try again."
    finally:
        await client.aclose()

    try:
        with transaction(ctx.post_draft_repo.conn):
            ctx.post_draft_repo.mark_sent(
                ctx.caller_user_id,
                draft.id,
                sent_by_user_bot_id=bot.id,
                sent_channel_id=resolved_channel_id,
                mattermost_post_id=mattermost_post_id,
            )
            ctx.audit_repo.record(
                caller_user_id=ctx.caller_user_id,
                caller_username=ctx.caller_username,
                draft_id=draft.id,
                user_bot_id=bot.id,
                bot_user_id=bot.bot_user_id,
                bot_username=bot.bot_username,
                channel_link=channel_link,
                resolved_channel_id=resolved_channel_id,
                resolved_team_name=channel.team_name,
                resolved_channel_name=channel.channel_name,
                message_sha256=draft.message_sha256,
                status="success",
                mattermost_post_id=mattermost_post_id,
                error_code=None,
                error_message=None,
            )
    except Exception:
        return (
            "Mattermost accepted the post, but the local status update failed. "
            "Please contact an administrator before retrying this draft."
        )
    return f"Draft #{draft.id} published."


@asynccontextmanager
async def _send_lock(owner_user_id: str, draft_id: int) -> AsyncIterator[None]:
    key = (owner_user_id, draft_id)
    async with _SEND_LOCKS_GUARD:
        lock = _SEND_LOCKS.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _SEND_LOCKS[key] = lock

    await lock.acquire()
    try:
        yield
    finally:
        lock.release()


def _parse_args(args: ParsedArgs) -> tuple[int, str, str] | None:
    if len(args.positional) != 1 or set(args.flags) != {"bot", "channel"}:
        return None

    bot_alias = args.flags["bot"]
    channel_link = args.flags["channel"]
    if not isinstance(bot_alias, str) or not bot_alias:
        return None
    if not isinstance(channel_link, str) or not channel_link:
        return None

    try:
        draft_id = int(args.positional[0])
    except ValueError:
        return None
    if draft_id <= 0:
        return None

    return draft_id, bot_alias, channel_link


def _record_failed_audit(
    ctx: CommandContext,
    *,
    draft: PostDraft,
    bot: UserBot,
    channel_link: str,
    channel: ChannelLink | None,
    resolved_channel_id: str | None,
    error_code: str,
    error_message: str,
) -> None:
    ctx.audit_repo.record(
        caller_user_id=ctx.caller_user_id,
        caller_username=ctx.caller_username,
        draft_id=draft.id,
        user_bot_id=bot.id,
        bot_user_id=bot.bot_user_id,
        bot_username=bot.bot_username,
        channel_link=channel_link,
        resolved_channel_id=resolved_channel_id,
        resolved_team_name=channel.team_name if channel is not None else None,
        resolved_channel_name=channel.channel_name if channel is not None else None,
        message_sha256=draft.message_sha256,
        status="failed",
        mattermost_post_id=None,
        error_code=error_code,
        error_message=error_message,
    )


def _record_failed_audit_safely(
    ctx: CommandContext,
    *,
    draft: PostDraft,
    bot: UserBot,
    channel_link: str,
    channel: ChannelLink | None,
    resolved_channel_id: str | None,
    error_code: str,
    error_message: str,
) -> None:
    with suppress(Exception):
        _record_failed_audit(
            ctx,
            draft=draft,
            bot=bot,
            channel_link=channel_link,
            channel=channel,
            resolved_channel_id=resolved_channel_id,
            error_code=error_code,
            error_message=error_message,
        )


def _safe_error_message(exc: BaseException) -> str:
    if isinstance(exc, MattermostError):
        return f"Mattermost API returned {exc.status}."
    if isinstance(exc, httpx.HTTPError):
        return "Mattermost request failed."
    return "Mattermost response was invalid."


def _string_field(payload: dict[str, Any], field: str) -> str | None:
    value = payload.get(field)
    if isinstance(value, str) and value:
        return value
    return None
