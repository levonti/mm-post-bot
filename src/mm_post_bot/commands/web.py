from datetime import UTC, datetime

from ..services.web_auth import build_login_url, create_login_token
from .access import require_approved_user
from .context import CommandContext
from .parser import ParsedArgs


async def handle(ctx: CommandContext, args: ParsedArgs) -> str:
    access_error = require_approved_user(ctx)
    if access_error is not None:
        return access_error

    if args.positional or args.flags:
        return ctx.t("web.usage")

    if ctx.channel_type != "D":
        return ctx.t("web.dm_only")

    raw_token = create_login_token(
        token_repo=ctx.web_login_token_repo,
        owner_user_id=ctx.caller_user_id,
        now=datetime.now(UTC),
        ttl_seconds=ctx.web_login_token_ttl_seconds,
    )
    url = build_login_url(ctx.web_base_url, raw_token)
    return ctx.t("web.link", url=url)
