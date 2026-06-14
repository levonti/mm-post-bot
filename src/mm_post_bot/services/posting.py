import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, suppress
from dataclasses import dataclass
from typing import Any

import httpx

from ..commands.context import CommandContext
from ..db import transaction
from ..mm_client import MattermostClient, MattermostError
from ..repository import PostDraft, UserBot, UserChannel, UserPostDefault
from ..security import decrypt_token, hash_message


class DraftMessageEmpty(ValueError):  # noqa: N818
    pass


class PublishError(RuntimeError):
    def __init__(self, code: str, message_key: str) -> None:
        super().__init__(message_key)
        self.code = code
        self.message_key = message_key


@dataclass(frozen=True, slots=True)
class TargetRequest:
    bot_alias: str | None
    channel_alias: str | None


@dataclass(frozen=True, slots=True)
class TargetOptions:
    bots: list[UserBot]
    channels: list[UserChannel]
    default: UserPostDefault | None
    has_stale_default: bool


@dataclass(frozen=True, slots=True)
class PublishDraftRequest:
    draft_id: int
    target: TargetRequest


@dataclass(frozen=True, slots=True)
class PublishDraftResult:
    draft_id: int
    mattermost_post_id: str
    bot: UserBot
    channel: UserChannel


@dataclass(frozen=True, slots=True)
class _ResolvedTargets:
    bot: UserBot
    channel: UserChannel


# Keep locks for the process lifetime so a draft lock is never replaced while waiters exist.
_SEND_LOCKS: dict[tuple[str, int], asyncio.Lock] = {}
_SEND_LOCKS_GUARD = asyncio.Lock()


def create_draft(ctx: CommandContext, message: str) -> PostDraft:
    normalized = _normalize_message(message)
    return ctx.post_draft_repo.create(
        owner_user_id=ctx.caller_user_id,
        message=normalized,
        message_sha256=hash_message(normalized),
    )


def update_draft_message(ctx: CommandContext, draft_id: int, message: str) -> PostDraft:
    normalized = _normalize_message(message)
    return ctx.post_draft_repo.update_message(
        ctx.caller_user_id,
        draft_id,
        message=normalized,
        message_sha256=hash_message(normalized),
    )


def list_target_options(ctx: CommandContext) -> TargetOptions:
    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    return TargetOptions(
        bots=ctx.user_bot_repo.list_for_owner(ctx.caller_user_id),
        channels=ctx.user_channel_repo.list_for_owner(ctx.caller_user_id),
        default=default,
        has_stale_default=default is None
        and ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id),
    )


async def publish_draft(
    ctx: CommandContext,
    request: PublishDraftRequest,
) -> PublishDraftResult:
    default = _resolve_default(ctx, request.target)

    async with _send_lock(ctx.caller_user_id, request.draft_id):
        return await _publish_draft_locked(ctx, request, default)


async def _publish_draft_locked(
    ctx: CommandContext,
    request: PublishDraftRequest,
    default: UserPostDefault | None,
) -> PublishDraftResult:
    try:
        draft = ctx.post_draft_repo.get_for_owner(ctx.caller_user_id, request.draft_id)
    except LookupError as exc:
        raise PublishError("draft_unavailable", "send.draft_unavailable") from exc

    if draft.status != "draft":
        raise PublishError("draft_unavailable", "send.draft_unavailable")

    resolved = _resolve_targets(ctx, request.target, default, draft)
    bot = resolved.bot
    channel = resolved.channel

    try:
        token = decrypt_token(bot.token_ciphertext, ctx.token_encryption_key)
    except Exception as exc:
        _record_failed_audit_safely(
            ctx,
            draft=draft,
            bot=bot,
            channel_alias=channel.alias,
            resolved_channel_id=channel.channel_id,
            error_code="token_decrypt",
            error_message="Bot token storage is misconfigured.",
        )
        raise PublishError("storage_misconfigured", "send.storage_misconfigured") from exc

    client = MattermostClient(ctx.mm_rest_base, token, verify_ssl=ctx.mm_verify_ssl)
    try:
        try:
            post_payload = await client.create_post(channel.channel_id, draft.message)
            mattermost_post_id = _string_field(post_payload, "id")
            if mattermost_post_id is None:
                raise ValueError("post response did not include an id")
        except (MattermostError, httpx.HTTPError, ValueError) as exc:
            _record_failed_audit_safely(
                ctx,
                draft=draft,
                bot=bot,
                channel_alias=channel.alias,
                resolved_channel_id=channel.channel_id,
                error_code="mattermost_post",
                error_message=_safe_error_message(exc),
            )
            raise PublishError("publish_failed", "send.publish_failed") from exc
    finally:
        await client.aclose()

    try:
        with transaction(ctx.post_draft_repo.conn):
            ctx.post_draft_repo.mark_sent(
                ctx.caller_user_id,
                draft.id,
                sent_by_user_bot_id=bot.id,
                sent_channel_id=channel.channel_id,
                mattermost_post_id=mattermost_post_id,
            )
            ctx.audit_repo.record(
                caller_user_id=ctx.caller_user_id,
                caller_username=ctx.caller_username,
                draft_id=draft.id,
                user_bot_id=bot.id,
                bot_user_id=bot.bot_user_id,
                bot_username=bot.bot_username,
                channel_link=channel.alias,
                resolved_channel_id=channel.channel_id,
                resolved_team_name=None,
                resolved_channel_name=None,
                message_sha256=draft.message_sha256,
                status="success",
                mattermost_post_id=mattermost_post_id,
                error_code=None,
                error_message=None,
            )
    except Exception as exc:
        raise PublishError("local_update_failed", "send.local_update_failed") from exc

    return PublishDraftResult(
        draft_id=draft.id,
        mattermost_post_id=mattermost_post_id,
        bot=bot,
        channel=channel,
    )


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


def _normalize_message(message: str) -> str:
    normalized = message.strip()
    if not normalized:
        raise DraftMessageEmpty()
    return normalized


def _resolve_default(
    ctx: CommandContext,
    target: TargetRequest,
) -> UserPostDefault | None:
    if target.bot_alias is not None and target.channel_alias is not None:
        return None

    default = ctx.user_post_default_repo.get_for_owner(ctx.caller_user_id)
    if default is None:
        if ctx.user_post_default_repo.has_for_owner(ctx.caller_user_id):
            raise PublishError("default_stale", "send.default_stale")
        raise PublishError("defaults_missing", "send.defaults_missing")

    return default


def _resolve_targets(
    ctx: CommandContext,
    target: TargetRequest,
    default: UserPostDefault | None,
    draft: PostDraft,
) -> _ResolvedTargets:
    if target.bot_alias is None:
        if default is None:
            raise PublishError("defaults_missing", "send.defaults_missing")
        bot = default.bot
    else:
        try:
            bot = ctx.user_bot_repo.get_by_owner_and_alias(ctx.caller_user_id, target.bot_alias)
        except LookupError as exc:
            raise PublishError("bot_not_found", "send.bot_not_found") from exc

    if target.channel_alias is None:
        if default is None:
            raise PublishError("defaults_missing", "send.defaults_missing")
        channel = default.channel
    else:
        try:
            channel = ctx.user_channel_repo.get_by_owner_and_alias(
                ctx.caller_user_id,
                target.channel_alias,
            )
        except LookupError as exc:
            _record_failed_audit_safely(
                ctx,
                draft=draft,
                bot=bot,
                channel_alias=target.channel_alias,
                resolved_channel_id=None,
                error_code="channel_alias",
                error_message="Unknown channel alias.",
            )
            raise PublishError("channel_not_found", "send.channel_not_found") from exc

    return _ResolvedTargets(bot=bot, channel=channel)


def _record_failed_audit(
    ctx: CommandContext,
    *,
    draft: PostDraft,
    bot: UserBot,
    channel_alias: str,
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
        channel_link=channel_alias,
        resolved_channel_id=resolved_channel_id,
        resolved_team_name=None,
        resolved_channel_name=None,
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
    channel_alias: str,
    resolved_channel_id: str | None,
    error_code: str,
    error_message: str,
) -> None:
    with suppress(Exception):
        _record_failed_audit(
            ctx,
            draft=draft,
            bot=bot,
            channel_alias=channel_alias,
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
