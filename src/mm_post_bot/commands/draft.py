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
        return "Usage: !draft"

    expires_at = datetime.now(UTC) + CAPTURE_WINDOW
    ctx.draft_capture_repo.start(owner_user_id=ctx.caller_user_id, expires_at=expires_at)
    return "Draft capture started. Please send the post body in this direct message."


async def cancel(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if args.positional:
        return "Usage: !draft cancel"

    ctx.draft_capture_repo.clear(ctx.caller_user_id)
    return "Draft capture cancelled."


async def list_drafts(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if args.positional:
        return "Usage: !draft list"

    drafts = ctx.post_draft_repo.list_for_owner(ctx.caller_user_id)
    if not drafts:
        return "No saved drafts."

    return "\n".join(f"#{draft.id} - {_preview(draft.message)}" for draft in drafts)


async def show(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if len(args.positional) != 1:
        return "Usage: !draft show <draft_id>"

    draft_id = _parse_draft_id(args.positional[0])
    if draft_id is None:
        return "Usage: !draft show <draft_id>"

    try:
        draft = ctx.post_draft_repo.get_for_owner(ctx.caller_user_id, draft_id)
    except LookupError:
        return "Draft not found."

    if draft.status != "draft":
        return "Draft not found."

    return f"Draft #{draft.id}:\n{draft.message}"


async def delete(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    dm_error = _require_dm(ctx)
    if dm_error is not None:
        return dm_error

    if len(args.positional) != 1:
        return "Usage: !draft delete <draft_id>"

    draft_id = _parse_draft_id(args.positional[0])
    if draft_id is None:
        return "Usage: !draft delete <draft_id>"

    try:
        draft = ctx.post_draft_repo.get_for_owner(ctx.caller_user_id, draft_id)
    except LookupError:
        return "Draft not found."

    if draft.status != "draft":
        return "Draft not found."

    ctx.post_draft_repo.soft_delete(ctx.caller_user_id, draft_id)
    return f"Draft #{draft_id} deleted."


def _require_dm(ctx: CommandContext) -> str | None:
    if ctx.channel_type == "D":
        return None
    return "Please use draft commands in a direct message."


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
