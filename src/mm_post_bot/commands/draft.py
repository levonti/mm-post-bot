from datetime import UTC, datetime, timedelta

from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs

CAPTURE_WINDOW = timedelta(minutes=30)


async def start(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if args.positional:
        return ctx.t("draft.start_usage")

    expires_at = datetime.now(UTC) + CAPTURE_WINDOW
    ctx.draft_capture_repo.start(owner_user_id=ctx.caller_user_id, expires_at=expires_at)
    return ctx.t("draft.started")


async def cancel(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if args.positional:
        return ctx.t("draft.cancel_usage")

    ctx.draft_capture_repo.clear(ctx.caller_user_id)
    return ctx.t("draft.cancelled")


async def list_drafts(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if args.positional:
        return ctx.t("draft.list_usage")

    drafts = ctx.post_draft_repo.list_for_owner(ctx.caller_user_id)
    if not drafts:
        return ctx.t("draft.list_empty")

    return "\n".join(f"#{draft.id} - {_preview(draft.message)}" for draft in drafts)


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if len(args.positional) != 1:
        return ctx.t("draft.show_usage")

    draft_id = _parse_draft_id(args.positional[0])
    if draft_id is None:
        return ctx.t("draft.show_usage")

    try:
        draft = ctx.post_draft_repo.get_for_owner(ctx.caller_user_id, draft_id)
    except LookupError:
        return ctx.t("draft.not_found")

    if draft.status != "draft":
        return ctx.t("draft.not_found")

    return ctx.t("draft.show", draft_id=draft.id, message=draft.message)


async def delete(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if len(args.positional) != 1:
        return ctx.t("draft.delete_usage")

    draft_id = _parse_draft_id(args.positional[0])
    if draft_id is None:
        return ctx.t("draft.delete_usage")

    try:
        draft = ctx.post_draft_repo.get_for_owner(ctx.caller_user_id, draft_id)
    except LookupError:
        return ctx.t("draft.not_found")

    if draft.status != "draft":
        return ctx.t("draft.not_found")

    ctx.post_draft_repo.soft_delete(ctx.caller_user_id, draft_id)
    return ctx.t("draft.deleted", draft_id=draft_id)


def _require_dm(ctx: CommandContext) -> str | None:
    if ctx.channel_type == "D":
        return None
    return ctx.t("draft.dm_only")


def _parse_draft_id(raw: str) -> int | None:
    try:
        draft_id = int(raw)
    except ValueError:
        return None
    return draft_id if draft_id > 0 else None


def _preview(message: str) -> str:
    first_line = message.splitlines()[0].strip() if message.splitlines() else ""
    if len(first_line) <= 80:
        return first_line
    return f"{first_line[:77]}..."
